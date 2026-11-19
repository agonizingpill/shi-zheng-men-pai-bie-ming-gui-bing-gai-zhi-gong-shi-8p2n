from sqlalchemy import update
from .models import Entrance,Redirect,Proposal,Notice,RoadChange,RoadSegment,RoadChangeHistory
from .common import *

def resolve_root(s,id):
 get(s,Entrance,id);chain=[id];cur=id;mapping={x.source_id:x.target_id for x in rows(s,Redirect) if x.state=='active'}
 while cur in mapping:
  cur=mapping[cur]
  if cur in chain:fail('重定向成环')
  chain.append(cur)
 return {'requested_id':id,'canonical_id':cur,'chain':chain}

def activate(s,p,now):
 if any(x.state=='active' and x.source_id==p.source_id for x in rows(s,Redirect)):fail('入口已有生效归并，请先回滚')
 if p.source_id in resolve_root(s,p.target_id)['chain']:fail('重定向成环，拒绝生效')
 r=Redirect(source_id=p.source_id,target_id=p.target_id,proposal_id=p.id,created=now);s.add(r);s.flush();return r

def rollback(s,id,d):
 lock(s);r=get(s,Redirect,id)
 if r.state!='active':fail('该映射已经回滚')
 r.state='rolled_back';r.reason=d['reason'];get(s,Proposal,r.proposal_id).state='rolled_back'
 for n in rows(s,Notice):
  if n.proposal_id==r.proposal_id:n.state='revoked'
 return r

def returned(s):
 """公示后退回待核定的提案：原公示保留原样可查，不指向别处；只允许重新公示或拆分。"""
 out=[]
 for n in rows(s,Notice):
  if n.state!='returned':continue
  p=get(s,Proposal,n.proposal_id)
  out.append({'proposal_id':p.id,'notice_id':n.id,'proposal_code':p.code,'notice':dump(n),
              'source_id':n.source_id,'target_id':n.target_id,'current_source_id':p.source_id,'current_target_id':p.target_id,
              'proposal_state':p.state,'reason':n.returned_reason,'split_allowed':p.state!='active'})
 return out
