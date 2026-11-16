import os,json
import redis
from fastapi import APIRouter,Depends,HTTPException,Response
from src.config.database import db
from src.models.entities import User,Settlement,Pivot,Review,Audit,GateEvent,Verification,PresenceInterval,GateAnomaly
from src.schemas.business import Login,SettlementInput,PivotInput,ReviewInput,ReviewEdit,GateBatchInput
from src.middlewares.auth import current,editor,admin
from src.utils.security import verify,token
from src.services.business import audit,dump
from src.services.settlements import save
from src.services.analysis import key
from src.services.verification import ingest,invalidate_seats,retry as retry_verification,publish as publish_verification
from src.controllers.business import ensure_pivot,ensure_review,ensure_verification,cell
router=APIRouter()
@router.post('/auth/login')
def login(data:Login,s=Depends(db)):
 u=s.query(User).filter_by(email=data.email).first()
 if not u or not verify(data.password,u.password):raise HTTPException(401,'账号或密码错误')
 return {'token':token(u),'user':dump(u)}
@router.get('/me')
def me(u=Depends(current)):return dump(u)
@router.get('/settlements')
def settlements(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Settlement).order_by(Settlement.id).all()]
@router.post('/settlements')
def create(data:SettlementInput,u=Depends(editor),s=Depends(db)):
 r=save(s,data);audit(s,u,'录入结算 '+r['code']);return r
@router.put('/settlements/{i}')
def edit(i:int,data:SettlementInput,u=Depends(editor),s=Depends(db)):
 old=s.get(Settlement,i);old_seats=old.seats if old else None
 r=save(s,data,i)
 if old_seats is not None and old_seats!=r['seats']:
  n=invalidate_seats(s,r['code'])
  if n:audit(s,u,f"座位修订 {r['code']}：{n} 个核验批次失效")
 audit(s,u,'修订结算 '+str(i));return r
@router.get('/pivots')
def pivots(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Pivot).order_by(Pivot.id.desc()).all()]
@router.post('/pivots')
def submit(data:PivotInput,u=Depends(editor),s=Depends(db)):
 rows=[dump(r) for r in s.query(Settlement).order_by(Settlement.id).all()]
 r=Pivot(**data.model_dump(),result={'snapshot':rows});s.add(r);s.commit()
 try:redis.Redis.from_url(os.environ['REDIS_URL']).rpush('stage:pivots',r.id)
 except redis.RedisError:r.state='failed';r.error='队列暂不可用，请恢复后新建透视';s.commit();raise HTTPException(503,r.error)
 audit(s,u,'提交透视 '+str(r.id));return dump(r)
@router.get('/pivots/{i}')
def detail(i:int,u=Depends(current),s=Depends(db)):return dump(ensure_pivot(s,i))
@router.get('/pivots/{i}/drill')
def drill(i:int,row_key:str,col_key:str,u=Depends(current),s=Depends(db)):
 r,c=cell(s,i,row_key,col_key)
 return {'cell':c,'rows':[x for x in r.result['snapshot'] if key(x,r.row_dim)==row_key and key(x,r.col_dim)==col_key]}
@router.get('/pivots/{i}/export')
def export(i:int,u=Depends(current),s=Depends(db)):
 r=ensure_pivot(s,i)
 if r.state!='done':raise HTTPException(409,'仅成功透视可以导出')
 return Response(json.dumps(dump(r),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="stage-pivot-{i}.json"'})
@router.get('/reviews')
def reviews(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Review).order_by(Review.id.desc()).all()]
@router.post('/reviews')
def review(data:ReviewInput,u=Depends(editor),s=Depends(db)):
 run,c=cell(s,data.pivot_id,data.row_key,data.col_key)
 r=Review(**data.model_dump(),book_cents=c['net_cents'],difference_cents=data.expected_cents-c['net_cents']);s.add(r);s.commit();audit(s,u,'起草差异复核 '+str(r.id));return dump(r)
@router.put('/reviews/{i}')
def edit_review(i:int,data:ReviewEdit,u=Depends(editor),s=Depends(db)):
 r=ensure_review(s,i)
 if r.status!='draft':raise HTTPException(409,'已签核复核单不可覆盖，请新建复核')
 r.expected_cents=data.expected_cents;r.difference_cents=data.expected_cents-r.book_cents;r.note=data.note;s.commit();audit(s,u,'修改差异复核 '+str(i));return dump(r)
@router.post('/reviews/{i}/approve')
def approve(i:int,u=Depends(admin),s=Depends(db)):
 r=ensure_review(s,i)
 if r.status!='draft':raise HTTPException(409,'已签核复核单不可重复签核')
 r.status='approved';s.commit();audit(s,u,'签核差异复核 '+str(i));return dump(r)
@router.post('/gate-events')
def gate_ingest(data:GateBatchInput,u=Depends(editor),s=Depends(db)):
 accepted,duplicates,sessions=ingest(s,data.records)
 audit(s,u,f"收录闸机记录 {len(accepted)} 条（去重 {len(duplicates)}）场次 "+('、'.join(sessions) or '无'))
 return {'accepted':len(accepted),'duplicates':duplicates,'sessions':sessions}
@router.get('/gate-events')
def gate_events(session:str|None=None,u=Depends(current),s=Depends(db)):
 q=s.query(GateEvent)
 if session:q=q.filter_by(session=session)
 return [dump(r) for r in q.order_by(GateEvent.happened_at,GateEvent.event_no).limit(500)]
@router.get('/verifications')
def verifications(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Verification).order_by(Verification.id.desc()).all()]
@router.get('/verifications/{i}')
def verification(i:int,u=Depends(current),s=Depends(db)):return dump(ensure_verification(s,i))
@router.get('/verifications/{i}/intervals')
def intervals(i:int,ticket:str|None=None,u=Depends(current),s=Depends(db)):
 ensure_verification(s,i)
 q=s.query(PresenceInterval).filter_by(verification_id=i)
 if ticket:q=q.filter_by(ticket=ticket)
 return [dump(r) for r in q.order_by(PresenceInterval.ticket,PresenceInterval.entered_at).limit(1000)]
@router.get('/verifications/{i}/anomalies')
def anomalies(i:int,u=Depends(current),s=Depends(db)):
 ensure_verification(s,i)
 return [dump(r) for r in s.query(GateAnomaly).filter_by(verification_id=i).order_by(GateAnomaly.happened_at).limit(1000)]
@router.post('/verifications/{i}/retry')
def ver_retry(i:int,u=Depends(editor),s=Depends(db)):
 r=retry_verification(s,ensure_verification(s,i));audit(s,u,'重新计算核验 '+str(i));return r
@router.post('/verifications/{i}/publish')
def ver_publish(i:int,u=Depends(editor),s=Depends(db)):
 r=publish_verification(s,ensure_verification(s,i));audit(s,u,f"发布核验 {i}，接管场次 {r['session']} 核验数");return r
@router.get('/verifications/{i}/export')
def ver_export(i:int,u=Depends(current),s=Depends(db)):
 v=ensure_verification(s,i)
 if not v.result:raise HTTPException(409,'核验尚无计算结果，无法下载依据')
 payload={'verification':dump(v),'events':[dump(r) for r in s.query(GateEvent).filter_by(session=v.session).order_by(GateEvent.happened_at,GateEvent.event_no).all()],'intervals':[dump(r) for r in s.query(PresenceInterval).filter_by(verification_id=i).order_by(PresenceInterval.ticket,PresenceInterval.entered_at).all()],'anomalies':[dump(r) for r in s.query(GateAnomaly).filter_by(verification_id=i).order_by(GateAnomaly.happened_at).all()]}
 return Response(json.dumps(payload,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="gate-verification-{i}.json"'})
@router.get('/audits')
def audits(u=Depends(admin),s=Depends(db)):return [dump(r) for r in s.query(Audit).order_by(Audit.id.desc()).limit(100)]
