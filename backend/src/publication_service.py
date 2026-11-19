from datetime import timedelta
from fastapi import HTTPException
from .models import Proposal,Notice,Objection,Alias,Evidence,Entrance
from .common import *
from .proposal_service import pair
from .directory_service import activate
from . import road_service as road

def notice_basis(s,p):return road.basis(s,p.source_id,p.target_id)

def publish(s,d):
 r=lock(s);p=get(s,Proposal,d['proposal_id'])
 if p.state not in ('draft','returned'):fail('只可公示草稿或退回待核定的提案')
 pair(s,p.source_id,p.target_id)
 aliases={x.id for x in rows(s,Alias) if x.entrance_id==p.source_id}
 if not any(x.alias_id in aliases for x in rows(s,Evidence)):fail('来源入口缺少别名证据，不可公示')
 b=notice_basis(s,p)
 if b['recheck']:fail('沿革书证与备案不一致，需先复核：'+'；'.join(b['recheck']))
 start=timestamp(r.now)
 n=Notice(proposal_id=p.id,starts=start.isoformat(),ends=(start+timedelta(days=d['days'])).isoformat(),source_id=p.source_id,target_id=p.target_id,basis=b)
 s.add(n);p.state='public';p.returned_reason='';s.flush();return n

def effective(s,id):
 r=lock(s);n=get(s,Notice,id);p=get(s,Proposal,n.proposal_id)
 if n.state!='public' or p.state!='public':fail('公示不是待生效状态')
 if timestamp(r.now)<timestamp(n.ends):fail('公示期限未满')
 if any(x.proposal_id==p.id and x.state=='open' for x in rows(s,Objection)):fail('居民异议未结，不能生效')
 b=notice_basis(s,p)
 moved=[]
 for eid,v in b['entrances'].items():
  b_old=(n.basis or {}).get('entrances',{})
  old=b_old.get(str(eid)) or b_old.get(eid)
  if not old or old.get('fingerprint')!=v['fingerprint'] or old.get('street')!=v['street'] or old.get('number')!=v['number']:
   moved.append(get(s,Entrance,eid))
 if moved or n.source_id!=p.source_id or n.target_id!=p.target_id:
  n.state='returned';n.returned_reason='归属在公示后发生变化，退回重新核定'+(f"（{'、'.join(x.code for x in moved)}）" if moved else '')
  p.state='returned';p.returned_reason=n.returned_reason
  return n
 pair(s,p.source_id,p.target_id)
 try:redirect=activate(s,p,r.now)
 except HTTPException:
  # 生效前的最后一道门（已有生效映射、成环）也不能把原公示改指别处：退回，保留原公示。
  # 重新公示后由新公示承担新的生效尝试；旧公示保持 returned 与原依据。
  n.state='returned';n.returned_reason='生效核验未通过，退回重新核定，原公示保留原指向'
  p.state='returned';p.returned_reason=n.returned_reason
  return n
 n.state='effective';p.state='active';return redirect

def advance(s,d):
 r=lock(s);new=timestamp(d['now'])
 if new<timestamp(r.now):fail('演示时钟不可倒退')
 r.now=new.isoformat();return r
