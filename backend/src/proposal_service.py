from .models import Entrance,Alias,Evidence,Proposal,Objection,Notice
from .common import *
from . import road_service as road

def pair(s,a,b):
 x=get(s,Entrance,a);y=get(s,Entrance,b)
 if a==b:fail('不能归并到自身')
 if x.number!=y.number:fail('门牌数字冲突，不得归并')
 ax=road.attribution(s,x.id);ay=road.attribution(s,y.id)
 for e,a2 in ((x,ax),(y,ay)):
  if a2['status']=='pending':fail(f'入口 {e.code} 旧路名归属待核定，暂不能形成提案：{a2["reason"]}')
 if x.street!=y.street and not road.linked(dump(x),dump(y),ax,ay):fail('道路不符且沿革书证未能追认到同一现路，不得归并')
 return x,y

def snapshot_now(s):
 snap=road.snapshot(s);snap['names']=sorted(snap['names']);snap['old_names']=sorted(snap['old_names'])
 snap['changes']={str(k):v for k,v in snap['changes'].items()}
 return snap

def create(s,d):
 lock(s);pair(s,d['source_id'],d['target_id'])
 if d.get('candidate_id'):
  from .models import Candidate,MatchRun
  c=get(s,Candidate,d['candidate_id'])
  if c.state=='rejected':fail('候选已排除，请重新计算')
  if c.state=='pending':fail('候选沿革归属待核定，不能直接形成提案')
  if c.conflict:fail('候选数字冲突，不得形成提案')
  if (c.source_id,c.target_id)!=(d['source_id'],d['target_id']) and (c.target_id,c.source_id)!=(d['source_id'],d['target_id']):fail('提案门槛与候选不一致，请核对')
  run=get(s,MatchRun,c.run_id)
  if run.road_snapshot is not None and run.road_snapshot!=snapshot_now(s):fail('道路沿革在计算候选后已有更正，候选已过期，请重新计算')
  c.state='confirmed';c.review_note=d['reason']
 x=Proposal(**{k:v for k,v in d.items() if k!='candidate_id'});s.add(x);s.flush();return x

def object_to(s,d):
 lock(s);p=get(s,Proposal,d['proposal_id'])
 if p.state not in ['draft','public']:fail('只能在生效前提交异议')
 x=Objection(**d);s.add(x);s.flush();return x

def resolve(s,id,d):
 lock(s);x=get(s,Objection,id);p=get(s,Proposal,x.proposal_id)
 if x.state!='open' or p.state not in ['draft','public','returned']:fail('异议已经处理或提案不可复核')
 x.state='resolved';x.decision=d['decision'];x.resolution=d['resolution']
 if x.decision=='split':
  p.state='rejected'
  for n in rows(s,Notice):
   if n.proposal_id==p.id and n.state in ('public','returned'):n.state='withdrawn'
 return x

def split(s,d):
 """生效前拆分：拒绝原提案并撤销公示，两个入口都保留；已公示的原指向不变，不改成另一处。"""
 lock(s);p=get(s,Proposal,d['proposal_id'])
 if p.state not in ('draft','public','returned'):fail('只能拆分尚未生效的提案')
 if not d.get('reason'):fail('拆分须写明现场依据')
 p.state='rejected';p.returned_reason=d['reason']
 for o in rows(s,Objection):
  if o.proposal_id==p.id and o.state=='open':o.state='resolved';o.decision='split';o.resolution=d['reason']
 for n in rows(s,Notice):
  if n.proposal_id==p.id and n.state in ('public','returned'):n.state='withdrawn'
 return p
