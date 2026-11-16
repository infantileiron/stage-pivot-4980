from sqlalchemy import Column,Integer,BigInteger,String,JSON,Text,ForeignKey,UniqueConstraint
from src.config.database import Base
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True);email=Column(String(100),unique=True,nullable=False);password=Column(String(200));role=Column(String(20))
class Settlement(Base):
 __tablename__='settlements'
 id=Column(Integer,primary_key=True);code=Column(String(60),unique=True,nullable=False);day=Column(String(10));venue=Column(String(40));play=Column(String(60));channel=Column(String(30));gross_cents=Column(BigInteger);refund_cents=Column(BigInteger);fee_cents=Column(BigInteger);seats=Column(Integer);checked=Column(Integer);manual_checked=Column(Integer,nullable=True);verification_id=Column(Integer,nullable=True)
class Pivot(Base):
 __tablename__='pivots'
 id=Column(Integer,primary_key=True);name=Column(String(100));row_dim=Column(String(30));col_dim=Column(String(30));state=Column(String(20),default='queued');result=Column(JSON,nullable=True);error=Column(Text,default='')
class Review(Base):
 __tablename__='reviews'
 id=Column(Integer,primary_key=True);pivot_id=Column(Integer,ForeignKey('pivots.id'));row_key=Column(String(100));col_key=Column(String(100));book_cents=Column(BigInteger);expected_cents=Column(BigInteger);difference_cents=Column(BigInteger);note=Column(Text);status=Column(String(20),default='draft')
class Audit(Base):
 __tablename__='audits'
 id=Column(Integer,primary_key=True);actor=Column(String(100));action=Column(String(200));created=Column(String(40))
class GateEvent(Base):
 __tablename__='gate_events'
 id=Column(Integer,primary_key=True);device=Column(String(40),nullable=False);event_no=Column(String(40),nullable=False);ticket=Column(String(60));session=Column(String(60),index=True);happened_at=Column(String(40));action=Column(String(8));received_at=Column(String(40))
 __table_args__=(UniqueConstraint('device','event_no'),)
class Verification(Base):
 __tablename__='verifications'
 id=Column(Integer,primary_key=True);session=Column(String(60),unique=True,nullable=False);state=Column(String(20),default='pending');input_version=Column(Integer,default=1);computed_version=Column(Integer,nullable=True);retry_count=Column(Integer,default=0);result=Column(JSON,nullable=True);error=Column(Text,default='');created=Column(String(40));updated=Column(String(40))
class PresenceInterval(Base):
 __tablename__='presence_intervals'
 id=Column(Integer,primary_key=True);verification_id=Column(Integer,ForeignKey('verifications.id'),index=True);ticket=Column(String(60));entered_at=Column(String(40));exited_at=Column(String(40),nullable=True)
class GateAnomaly(Base):
 __tablename__='gate_anomalies'
 id=Column(Integer,primary_key=True);verification_id=Column(Integer,ForeignKey('verifications.id'),index=True);kind=Column(String(20));ticket=Column(String(60));happened_at=Column(String(40));reason=Column(String(300));device=Column(String(40));event_no=Column(String(40))
