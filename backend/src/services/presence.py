"""闸机在场区间重建与人数口径：纯函数，无数据库依赖。

口径：
- 每个票证的事件按 (时间, 事件号, 设备) 排序，乱序到达不影响结果；
- 未离场再次进场 = 重复进场（保留首次入场，不重复计人）；
- 无入场匹配的离场 = 孤立离场（到场事实成立，计入独立到场但不产生区间）；
- 独立到场人数 = 有在场区间的票证 ∪ 仅孤立离场的票证，去重计一次；
- 未闭环区间（最后仍入场状态）自最后入场起持续计入在场；
- 峰值 = 扫描线最大同时在场人数；超座时段 = 同时在场 > 座位数的最长连续区间。
"""
from datetime import datetime,timezone
def parse(t):
 d=datetime.fromisoformat(str(t).replace('Z','+00:00'))
 return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
def iso(d):return d.astimezone(timezone.utc).isoformat()
def compute(events,seats):
 """events: [dict(ticket,action,happened_at,device,event_no)]；seats: int。
 返回 (result, intervals, anomalies)。"""
 events=list(events);by={}
 for e in events:by.setdefault(e['ticket'],[]).append(e)
 intervals=[];anomalies=[]
 for ticket in sorted(by):
  inside=None
  for e in sorted(by[ticket],key=lambda e:(parse(e['happened_at']),str(e['event_no']),str(e['device']))):
   if e['action']=='in':
    if inside is None:inside=e
    else:anomalies.append({'kind':'duplicate_entry','ticket':ticket,'happened_at':e['happened_at'],'device':e['device'],'event_no':e['event_no'],'reason':f"票证{ticket}于{inside['happened_at']}进场后未记录离场，{e['happened_at']}再次进场：按重复进场处理，保留首次入场，不重复计人"})
   else:
    if inside is None:anomalies.append({'kind':'orphan_exit','ticket':ticket,'happened_at':e['happened_at'],'device':e['device'],'event_no':e['event_no'],'reason':f"票证{ticket}于{e['happened_at']}离场，但此前没有匹配的入场记录：计为孤立离场，独立到场仍计入一人"})
    else:intervals.append({'ticket':ticket,'entered_at':inside['happened_at'],'exited_at':e['happened_at']});inside=None
  if inside is not None:intervals.append({'ticket':ticket,'entered_at':inside['happened_at'],'exited_at':None})
 in_tickets={i['ticket'] for i in intervals}
 orphan_tickets={a['ticket'] for a in anomalies if a['kind']=='orphan_exit'}
 deltas={}
 for i in intervals:
  s=parse(i['entered_at']);deltas[s]=deltas.get(s,0)+1
  if i['exited_at']:e=parse(i['exited_at']);deltas[e]=deltas.get(e,0)-1
 cur=0;peak=0;peak_at=None;over=[];start=None;top=0
 for t in sorted(deltas):
  cur+=deltas[t]
  if cur>peak:peak,peak_at=cur,t
  if cur>seats:
   if start is None:start,top=t,cur
   else:top=max(top,cur)
  elif start is not None:over.append({'start':iso(start),'end':iso(t),'peak':top});start=None
 if start is not None:over.append({'start':iso(start),'end':None,'peak':top})
 result={'unique_count':len(in_tickets|orphan_tickets),'peak':peak,'peak_at':iso(peak_at) if peak_at else None,'over_capacity':over,'seats':seats,'event_count':len(events),'interval_count':len(intervals),'unclosed_count':sum(1 for i in intervals if not i['exited_at']),'anomaly_count':len(anomalies),'computed_at':iso(datetime.now(timezone.utc)),'method':'按票证以(时间,事件号,设备)排序重建在场区间，乱序到达不影响结果。未离场再次进场记重复进场并保留首次入场；无入场匹配的离场记孤立离场。独立到场=有区间的票证∪仅孤立离场的票证，去重计一次，重试不重复计人。未闭环区间自最后入场起持续计入在场。峰值=扫描线最大同时在场；超座时段=同时在场>座位数的最长连续区间，end为null表示持续至观测结束。'}
 return result,intervals,anomalies
