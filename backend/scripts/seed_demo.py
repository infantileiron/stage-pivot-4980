import os,random
from datetime import date,timedelta,datetime,timezone
from src.config.database import Base,engine,Session
from src.models.entities import User,Settlement,GateEvent,Verification
from src.utils.security import hash_password
from src.constants.enums import VENUES,CHANNELS
def gate_plan():
 """三个场次的演示闸机记录：重复进场、孤立离场、中途再入场、未闭环、超座。"""
 day='2026-09-01';ev=[]
 def t(mins):h,m=divmod(mins,60);return f'{day}T{h:02d}:{m:02d}:00+00:00'
 def add(device,seq,ticket,session,mins,action):ev.append(dict(device=device,event_no=f'E{seq:05d}',ticket=ticket,session=session,happened_at=t(mins),action=action))
 seq=10000
 for i in range(1,121):
  tk=f'T{i:04d}';seq+=1;add('GATE-A1',seq,tk,'YM-001',18*60+45+(i%40),'in')
  if i<=5:
   seq+=1;add('GATE-A1',seq,tk,'YM-001',20*60+i,'out');seq+=1;add('GATE-A1',seq,tk,'YM-001',20*60+25+i,'in');seq+=1;add('GATE-A1',seq,tk,'YM-001',21*60+40+i,'out')
  elif i in (6,7):
   seq+=1;add('GATE-A1',seq,tk,'YM-001',18*60+45+(i%40)+10,'in');seq+=1;add('GATE-A1',seq,tk,'YM-001',21*60+5+(i%45),'out')
  elif i in (8,9,10):pass
  else:seq+=1;add('GATE-A1',seq,tk,'YM-001',21*60+5+(i%45),'out')
 seq+=1;add('GATE-A1',seq,'T9001','YM-001',20*60+15,'out')
 seq=20000
 for i in range(1,61):
  tk=f'T1{i:03d}';seq+=1;add('GATE-B1',seq,tk,'YM-002',19*60+(i%30),'in');seq+=1;add('GATE-B1',seq,tk,'YM-002',21*60+10+(i%40),'out')
 seq=30000
 for i in range(1,151):
  tk=f'T2{i:03d}';seq+=1;add('GATE-C1',seq,tk,'YM-003',18*60+50+(i%35),'in');seq+=1;add('GATE-C1',seq,tk,'YM-003',21*60+20+(i%30),'out')
 return ev
def seed():
 Base.metadata.create_all(engine);rng=random.Random(3112)
 with Session() as s:
  for role in ('admin','analyst','viewer'):
   email=role+'@demo.local'
   if not s.query(User).filter_by(email=email).first():s.add(User(email=email,role=role,password=hash_password('Demo123!')))
  for i in range(180):
   code=f'YM-{i+1:03}';seats=[800,240,120][i%3];checked=rng.randint(seats//2,seats);gross=checked*rng.choice([8000,12000,18000]);refund=rng.randint(0,checked//10)*8000;fee=int((gross-refund)*[0,.07,.03][i%3])
   if not s.query(Settlement).filter_by(code=code).first():s.add(Settlement(code=code,day=(date(2026,9,1)+timedelta(days=i//3)).isoformat(),venue=VENUES[i%3],play=['渡口来信','星河漫游','一间书房','冬日序曲'][i%4],channel=CHANNELS[(i//3)%3],gross_cents=gross,refund_cents=refund,fee_cents=fee,seats=seats,checked=checked))
  now=datetime.now(timezone.utc).isoformat();added=0
  for e in gate_plan():
   if not s.query(GateEvent).filter_by(device=e['device'],event_no=e['event_no']).first():s.add(GateEvent(**e,received_at=now));added+=1
  s.flush();pending=[]
  for code in ('YM-001','YM-002','YM-003'):
   v=s.query(Verification).filter_by(session=code).first()
   if not v:v=Verification(session=code,state='pending',input_version=1,created=now,updated=now);s.add(v);s.flush()
   if v.state=='pending':pending.append(v.id)
  s.commit()
  if added or pending:
   try:
    from src.services.verification import enqueue
    for vid in pending:enqueue(vid)
   except Exception:pass
  s.commit();print({'users':s.query(User).count(),'settlements':s.query(Settlement).count(),'gate_events':s.query(GateEvent).count(),'verifications':s.query(Verification).count()})
if __name__=='__main__':seed()
