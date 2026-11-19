import os,redis
from fastapi import APIRouter,Depends
from .database import Session
from .models import *
from .schemas import *
from .security import current,allow
from .common import *
from . import entrance_service as entrance,proposal_service as proposal,publication_service as publication,directory_service as directory,road_service as road,worker
router=APIRouter()
def change(u,action,fn,supervisor=False):
 allow(u,*(['supervisor'] if supervisor else ['operator','supervisor']))
 with Session() as s:
  x=fn(s);log(s,u,action,dump(x));s.commit();return dump(x)
@router.get('/register')
def register(u=Depends(current)):
 with Session() as s:
  data={name:[dump(x) for x in rows(s,cls)] for name,cls in [('entrances',Entrance),('aliases',Alias),('evidence',Evidence),('runs',MatchRun),('candidates',Candidate),('proposals',Proposal),('objections',Objection),('notices',Notice),('redirects',Redirect),('clock',Registry)]}
  data['roads']=road.ledger(s);data['returned']=directory.returned(s)
  aliases=data['aliases'];evidence=data['evidence'];snap=road.snapshot(s)
  data['attribution']=[road.entrance_attribution(snap,e,aliases,evidence) for e in data['entrances']]
  return data
@router.get('/audit')
def audit(u=Depends(current)):
 with Session() as s:return [dump(x) for x in rows(s,Audit)]
@router.get('/roads')
def roads(u=Depends(current)):
 with Session() as s:return road.ledger(s)
@router.get('/roads/attribution/{entrance_id}')
def attribution(entrance_id:int,u=Depends(current)):
 with Session() as s:return road.attribution(s,entrance_id)
@router.get('/roads/trace')
def trace(old_name:str,number:int,dated:str='',u=Depends(current)):
 with Session() as s:return road.trace_segments(road.snapshot(s),old_name,number,dated)
@router.post('/roads/trace')
def trace_post(d:TraceIn,u=Depends(current)):
 with Session() as s:
  out=road.trace_segments(road.snapshot(s),d.old_name,d.number,d.dated)
  log(s,u,'试算旧路追认',out['status']+' '+out['reason']);s.commit();return out
@router.post('/roads')
def rcreate(d:RoadChangeIn,u=Depends(current)):return change(u,'登记道路沿革',lambda s:road.register(s,d.model_dump(),u))
@router.post('/roads/{id}/correct')
def rcorrect(id:int,d:RoadCorrectIn,u=Depends(current)):return change(u,'更正道路沿革',lambda s:road.correct(s,id,d.model_dump(),u),True)
@router.post('/entrances')
def ecreate(d:EntranceIn,u=Depends(current)):return change(u,'登记入口',lambda s:entrance.create_entrance(s,d.model_dump()))
@router.patch('/entrances/{id}/location')
def locate(id:int,d:LocationIn,u=Depends(current)):return change(u,'补正坐标',lambda s:entrance.locate(s,id,d.model_dump()))
@router.post('/aliases')
def aliases(d:AliasIn,u=Depends(current)):return change(u,'登记别名',lambda s:entrance.alias(s,d.model_dump()))
@router.post('/evidence')
def evidence(d:EvidenceIn,u=Depends(current)):return change(u,'登记证据',lambda s:entrance.evidence(s,d.model_dump()))
@router.post('/matches')
def matching(u=Depends(current)):
 def create(s):lock(s);x=MatchRun(state='queued');s.add(x);s.flush();return x
 d=change(u,'匹配别名',create)
 try:redis.from_url(os.environ['REDIS_URL']).rpush('address:matching',d['id'])
 except Exception:
  # 队列不可达时退回进程内计算，避免登记后永远停在 queued。
  try:
   with Session() as s:lock(s);worker.process(s,d['id']);s.commit()
  except Exception:
   with Session() as s:x=s.get(MatchRun,d['id']);x.state='failed';x.error='匹配队列不可达，可重新提交';s.commit()
   fail('匹配队列不可达，可重新提交')
 return d
@router.post('/candidates/{id}/review')
def creview(id:int,d:CandidateReviewIn,u=Depends(current)):
 def fn(s):
  lock(s);c=get(s,Candidate,id)
  if c.state=='confirmed':fail('候选已形成提案，不能再排除')
  c.state=d.state;c.review_note=d.note;return c
 return change(u,'复核归并候选',fn)
@router.post('/proposals')
def pcreate(d:ProposalIn,u=Depends(current)):return change(u,'归并提案',lambda s:proposal.create(s,d.model_dump()))
@router.post('/proposals/{id}/split')
def psplit(id:int,d:SplitIn,u=Depends(current)):
 def fn(s):
  if d.proposal_id!=id:fail('提案编号不一致')
  return proposal.split(s,d.model_dump())
 return change(u,'拆分归并提案',fn)
@router.post('/objections')
def ocreate(d:ObjectionIn,u=Depends(current)):return change(u,'登记异议',lambda s:proposal.object_to(s,d.model_dump()))
@router.post('/objections/{id}/resolve')
def oresolve(id:int,d:ResolveIn,u=Depends(current)):return change(u,'复核异议',lambda s:proposal.resolve(s,id,d.model_dump()),True)
@router.post('/notices')
def ncreate(d:NoticeIn,u=Depends(current)):return change(u,'发布公示',lambda s:publication.publish(s,d.model_dump()),True)
@router.post('/notices/{id}/effective')
def neffect(id:int,u=Depends(current)):
 def fn(s):
  x=publication.effective(s,id)
  if isinstance(x,Notice):return x
  return x
 return change(u,'公示生效',fn,True)
@router.post('/clock')
def clock(d:ClockIn,u=Depends(current)):return change(u,'推进演示时钟',lambda s:publication.advance(s,d.model_dump()),True)
@router.get('/directory/{id}')
def lookup(id:int,u=Depends(current)):
 with Session() as s:return directory.resolve_root(s,id)
@router.get('/returned')
def returned(u=Depends(current)):
 with Session() as s:return directory.returned(s)
@router.post('/redirects/{id}/rollback')
def rollback(id:int,d:ReasonIn,u=Depends(current)):return change(u,'回滚目录',lambda s:directory.rollback(s,id,d.model_dump()),True)
