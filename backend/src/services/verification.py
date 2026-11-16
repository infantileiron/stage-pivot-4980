"""闸机核验批次编排：收录去重、失效、重算、发布接管结算核验。

一致性约定：
- 闸机记录按 (设备, 事件号) 唯一去重，重复提交/重试不重复计人；
- input_version 在每次新记录收录、座位修订时递增；计算只在该版本未变时才落库，
  过期计算拒绝覆盖（条件更新 0 行即放弃并沿原批次重算）；
- 发布与结算接管在同一事务提交，透视提交在独立事务快照读，整批要么全见要么不见；
- 失败/崩溃后 worker 启动恢复 pending/computing 原批次，不新建批次。
"""
import os,logging
from datetime import datetime,timezone
import redis
from sqlalchemy import tuple_
from fastapi import HTTPException
from src.config.database import Session
from src.models.entities import GateEvent,Verification,PresenceInterval,GateAnomaly,Settlement
from src.services.business import dump
from src.services.presence import compute
def now():return datetime.now(timezone.utc).isoformat()
def norm(dt):return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
def enqueue(vid):
 try:redis.Redis.from_url(os.environ['REDIS_URL']).rpush('stage:verifications',vid);return True
 except redis.RedisError:return False
def ingest(s,records):
 """整批收录：先校验场次，再去重插入，最后失效旧结果。返回 (accepted, duplicates, sessions)。"""
 sessions={r.session for r in records}
 known={c for (c,) in s.query(Settlement.code).filter(Settlement.code.in_(sessions))}
 missing=sessions-known
 if missing:raise HTTPException(422,'场次不存在，无法关联结算：'+'、'.join(sorted(missing)))
 pairs={(r.device,r.event_no) for r in records}
 existing={p for p in s.query(GateEvent.device,GateEvent.event_no).filter(tuple_(GateEvent.device,GateEvent.event_no).in_(list(pairs)))}
 accepted=[];duplicates=[];seen=set()
 for r in records:
  k=(r.device,r.event_no)
  if k in existing or k in seen:duplicates.append({'device':r.device,'event_no':r.event_no});continue
  seen.add(k);accepted.append(GateEvent(device=r.device,event_no=r.event_no,ticket=r.ticket,session=r.session,happened_at=norm(r.time),action=r.action,received_at=now()))
 s.add_all(accepted)
 touched={a.session for a in accepted}
 for code in touched:
  v=s.query(Verification).filter_by(session=code).first()
  if not v:v=Verification(session=code,state='pending',input_version=0,created=now(),updated=now());s.add(v);s.flush()
  v.input_version+=1;v.updated=now()
  if v.state in ('computed','published'):v.state='stale'
 s.commit()
 for code in touched:
  v=s.query(Verification).filter_by(session=code).first()
  if v.state=='pending':enqueue(v.id)
 return accepted,duplicates,sorted(touched)
def invalidate_seats(s,code):
 """座位修订：该场次所有核验批次输入版本递增，已计算/已发布的失效。返回失效批次数。"""
 n=0
 for v in s.query(Verification).filter_by(session=code).all():
  v.input_version+=1;v.updated=now()
  if v.state in ('computed','published'):v.state='stale';n+=1
 s.commit();return n
def run_verification(vid):
 """worker 入口：沿原批次计算；输入变化则放弃过期结果并重排队。"""
 with Session() as s:
  v=s.get(Verification,vid)
  if not v or v.state!='pending':return
  v.state='computing';v.computing_version=v.input_version;v.error='';v.updated=now();s.commit()
  version=v.computing_version
 try:
  with Session() as s:
   v=s.get(Verification,vid)
   st=s.query(Settlement).filter_by(code=v.session).first()
   seats=st.seats if st else 0
   events=[{'ticket':e.ticket,'action':e.action,'happened_at':e.happened_at,'device':e.device,'event_no':e.event_no} for e in s.query(GateEvent).filter_by(session=v.session).all()]
   result,intervals,anomalies=compute(events,seats)
   s.query(PresenceInterval).filter_by(verification_id=vid).delete()
   s.query(GateAnomaly).filter_by(verification_id=vid).delete()
   s.add_all([PresenceInterval(verification_id=vid,**i) for i in intervals])
   s.add_all([GateAnomaly(verification_id=vid,**a) for a in anomalies])
   n=s.query(Verification).filter(Verification.id==vid,Verification.state=='computing',Verification.input_version==version).update({'state':'computed','computed_version':version,'result':result,'error':'','updated':now()},synchronize_session=False)
   if n!=1:
    s.rollback()
    m=0
    with Session() as s2:
     m=s2.query(Verification).filter(Verification.id==vid,Verification.state=='computing').update({'state':'pending','updated':now()},synchronize_session=False);s2.commit()
    if m:enqueue(vid)
    return
   s.commit()
 except Exception as e:
  logging.exception('verification %s failed',vid)
  with Session() as s:
   v=s.get(Verification,vid)
   if v and v.state=='computing':v.state='failed';v.error=str(e)[:500];v.updated=now();s.commit()
def retry(s,v):
 """失败/失效后沿原批次重算：同一批次 id，结果整体替换，不重复计人。"""
 if v.state not in ('failed','stale'):raise HTTPException(409,'仅失败或已失效的核验批次可以重新计算')
 v.state='pending';v.input_version+=1;v.retry_count=(v.retry_count or 0)+1;v.updated=now();s.commit()
 enqueue(v.id)
 return dump(v)
def publish(s,v):
 """发布：超座阻止但保留事实；核验人数在同一事务接管结算 checked，原人工数保留在 manual_checked。"""
 if v.state!='computed':
  msg={'pending':'核验仍在待处理，计算完成后才能发布','computing':'核验计算中，完成后才能发布','published':'核验已发布，不能重复发布','failed':'核验计算失败，请重试后再发布','stale':'核验已因迟到事件或座位修订失效，请重新计算后再发布'}.get(v.state,'当前状态不能发布')
  raise HTTPException(409,msg)
 r=v.result or {}
 if r.get('over_capacity'):raise HTTPException(409,f"存在超座时段（峰值{r.get('peak')}人超过座位{r.get('seats')}），阻止发布；计算事实已保留，可下载依据")
 st=s.query(Settlement).filter_by(code=v.session).first()
 if not st:raise HTTPException(422,'结算场次不存在，无法接管核验人数')
 n=s.query(Verification).filter(Verification.id==v.id,Verification.state=='computed').update({'state':'published','updated':now()},synchronize_session=False)
 if n!=1:s.rollback();raise HTTPException(409,'核验状态已变化，请刷新后重试')
 if st.manual_checked is None:st.manual_checked=st.checked
 st.checked=r['unique_count'];st.verification_id=v.id
 s.commit();s.refresh(v);return dump(v)
