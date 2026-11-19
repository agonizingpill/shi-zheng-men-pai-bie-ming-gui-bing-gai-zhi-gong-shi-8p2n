from sqlalchemy import Column,Integer,String,Float,ForeignKey,JSON,UniqueConstraint
from .database import Base
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True);email=Column(String(160),unique=True,nullable=False);password=Column(String(160),nullable=False);role=Column(String(20),nullable=False)
class Registry(Base):
 __tablename__='registry'
 id=Column(Integer,primary_key=True);now=Column(String(32),nullable=False);road_revision=Column(Integer,default=0,nullable=False)
class Entrance(Base):
 __tablename__='entrances'
 id=Column(Integer,primary_key=True);code=Column(String(40),unique=True,nullable=False);street=Column(String(80),nullable=False);number=Column(Integer,nullable=False);label=Column(String(100),nullable=False);lat=Column(Float,nullable=False);lng=Column(Float,nullable=False)
class Alias(Base):
 __tablename__='aliases'
 id=Column(Integer,primary_key=True);entrance_id=Column(Integer,ForeignKey('entrances.id'),nullable=False);text=Column(String(120),unique=True,nullable=False);state=Column(String(20),default='verified',nullable=False)
class Evidence(Base):
 __tablename__='evidence'
 id=Column(Integer,primary_key=True);alias_id=Column(Integer,ForeignKey('aliases.id'),nullable=False);reference=Column(String(100),unique=True,nullable=False);description=Column(String(500),nullable=False);dated=Column(String(10),default='',nullable=False)
class RoadChange(Base):
 __tablename__='road_changes'
 id=Column(Integer,primary_key=True);code=Column(String(40),unique=True,nullable=False);kind=Column(String(20),nullable=False);state=Column(String(20),default='active',nullable=False);revision=Column(Integer,default=1,nullable=False);reason=Column(String(500),default='',nullable=False);created=Column(String(32),nullable=False)
class RoadSegment(Base):
 __tablename__='road_segments'
 id=Column(Integer,primary_key=True);change_id=Column(Integer,ForeignKey('road_changes.id'),nullable=False);old_name=Column(String(80),nullable=False);new_name=Column(String(80),nullable=False);from_number=Column(Integer,nullable=False);to_number=Column(Integer,nullable=False);effective=Column(String(10),nullable=False);revision=Column(Integer,default=1,nullable=False);state=Column(String(20),default='active',nullable=False)
class RoadChangeHistory(Base):
 __tablename__='road_change_history'
 id=Column(Integer,primary_key=True);change_id=Column(Integer,ForeignKey('road_changes.id'),nullable=False);revision=Column(Integer,nullable=False);snapshot=Column(JSON,nullable=False);reason=Column(String(500),nullable=False);actor=Column(String(160),nullable=False);created=Column(String(32),nullable=False)
class MatchRun(Base):
 __tablename__='match_runs'
 id=Column(Integer,primary_key=True);state=Column(String(20),default='queued');result=Column(JSON,nullable=True);error=Column(String(500),default='');road_snapshot=Column(JSON,nullable=True)
class Candidate(Base):
 __tablename__='candidates'
 id=Column(Integer,primary_key=True);run_id=Column(Integer,ForeignKey('match_runs.id'),nullable=False);source_id=Column(Integer,ForeignKey('entrances.id'),nullable=False);target_id=Column(Integer,ForeignKey('entrances.id'),nullable=False);similarity=Column(Float,nullable=False);conflict=Column(Integer,nullable=False);rank=Column(Integer,default=0,nullable=False);state=Column(String(20),default='ranked',nullable=False);reason=Column(String(500),default='',nullable=False);basis=Column(JSON,nullable=True);review_note=Column(String(500),default='',nullable=False)
class Proposal(Base):
 __tablename__='proposals'
 id=Column(Integer,primary_key=True);code=Column(String(40),unique=True,nullable=False);source_id=Column(Integer,ForeignKey('entrances.id'),nullable=False);target_id=Column(Integer,ForeignKey('entrances.id'),nullable=False);reason=Column(String(500),nullable=False);state=Column(String(20),default='draft',nullable=False);returned_reason=Column(String(500),default='',nullable=False)
class Objection(Base):
 __tablename__='objections'
 id=Column(Integer,primary_key=True);proposal_id=Column(Integer,ForeignKey('proposals.id'),nullable=False);code=Column(String(40),unique=True,nullable=False);note=Column(String(500),nullable=False);state=Column(String(20),default='open');decision=Column(String(30),default='');resolution=Column(String(500),default='')
class Notice(Base):
 __tablename__='notices'
 id=Column(Integer,primary_key=True);proposal_id=Column(Integer,ForeignKey('proposals.id'),nullable=False);starts=Column(String(32),nullable=False);ends=Column(String(32),nullable=False);state=Column(String(20),default='public',nullable=False);source_id=Column(Integer,nullable=True);target_id=Column(Integer,nullable=True);basis=Column(JSON,nullable=True);returned_reason=Column(String(500),default='',nullable=False)
class Redirect(Base):
 __tablename__='redirects'
 id=Column(Integer,primary_key=True);source_id=Column(Integer,ForeignKey('entrances.id'),nullable=False);target_id=Column(Integer,ForeignKey('entrances.id'),nullable=False);proposal_id=Column(Integer,ForeignKey('proposals.id'),unique=True,nullable=False);state=Column(String(20),default='active');reason=Column(String(500),default='');created=Column(String(32),nullable=False)
class Audit(Base):
 __tablename__='audit'
 id=Column(Integer,primary_key=True);actor=Column(String(160),nullable=False);action=Column(String(100),nullable=False);detail=Column(String(500),nullable=False)
