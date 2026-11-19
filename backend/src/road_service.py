import hashlib,json
from sqlalchemy import select
from .models import RoadChange,RoadSegment,RoadChangeHistory,Entrance,Alias,Evidence,Notice,Proposal
from .common import *
from .numbers import number

def snapshot(s):
 """当前生效的沿革号段与改名头，全部是普通字典，便于匹配 worker 与提案校验复用。"""
 changes={x.id:dump(x) for x in rows(s,RoadChange)}
 segments=[dump(g) for g in s.scalars(select(RoadSegment).where(RoadSegment.state=='active').order_by(RoadSegment.id)).all()]
 names={g['old_name'] for g in segments}|{g['new_name'] for g in segments}
 old_names={g['old_name'] for g in segments}
 return {'changes':changes,'segments':segments,'names':names,'old_names':old_names}

def _covers(g,n):return g['from_number']<=n<=g['to_number']
def _view(g,changes):
 c=changes[g['change_id']]
 return {'segment_id':g['id'],'change_id':g['change_id'],'change_code':c['code'],'revision':g['revision'],
         'old_name':g['old_name'],'new_name':g['new_name'],'from_number':g['from_number'],'to_number':g['to_number'],'effective':g['effective']}
def _views(segs,changes):return [_view(g,changes) for g in segs]

def _component(segs,name_):
 """把与某个路名相连的号段取出来；同名重用会连在同一条时间线上。"""
 parent={}
 def find(x):
  parent.setdefault(x,x)
  while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
  return x
 def union(a,b):
  ra,rb=find(a),find(b)
  if ra!=rb:parent[ra]=rb
 for g in segs:union(g['old_name'],g['new_name'])
 if name_ not in parent:return []
 root=find(name_)
 return [g for g in segs if find(g['old_name'])==root]

def _timeline(segs):
 """按生效日期推演某号段的沿革时间线，旧名停用后可被别的路重新使用。
 返回 (occurrences, error)；occurrence = {name,start,end,out,next}，start=None 表示沿革簿记录起点。"""
 edges={}
 for g in sorted(segs,key=lambda g:(g['effective'],g['id'])):edges.setdefault((g['old_name'],g['effective']),[]).append(g)
 for (name,date),gs in edges.items():
  if len({g['new_name'] for g in gs})>1:
   return None,f'旧名 {name} 在 {date} 同日分裂到多个新路名，号段重叠，无法区分归属，留待核定'
 ordered=sorted(segs,key=lambda g:(g['effective'],g['id']))
 occs=[];by_name={}
 def new(name,start):
  o={'name':name,'start':start,'end':None,'out':None,'next':None};occs.append(o);by_name.setdefault(name,[]).append(o);return o
 active={}
 for g in ordered:
  t=day(g['effective']);o,w=g['old_name'],g['new_name']
  if o not in active:
   if o not in by_name:active[o]=new(o,None)
   else:return None,f'旧名 {o} 在 {g["effective"]} 已停用后再次出现，缺少重新启用记录，无法逐段追认，留待核定'
  cur=active.pop(o);cur['end']=t;cur['out']=g
  if w in active:target=active[w]
  else:target=new(w,t);active[w]=target
  cur['next']=target
 return occs,None

def trace_segments(snap,old_name,number_,dated):
 """按书证日期与门牌号逐段追认旧路，返回实际沿用的号段记录。
 status: none 无该旧名号段 / traced 已追认 / pending 留待核定。"""
 base={'old_name':old_name,'number':number_,'dated':dated or ''}
 allsegs=[g for g in snap['segments'] if _covers(g,number_)]
 segs=_component(allsegs,old_name)
 if not segs:return {**base,'status':'none','records':[],'reason':'沿革簿没有该旧名的适用号段'}
 if not dated:
  return {**base,'status':'pending','records':_views(segs,snap['changes']),'reason':'书证缺少日期，旧路名无法按号段追认，留待核定'}
 occs,err=_timeline(segs)
 if err:return {**base,'status':'pending','records':_views(segs,snap['changes']),'reason':err}
 dt=day(dated)
 valid=[o for o in occs if o['name']==old_name and (o['start'] is None or o['start']<=dt) and (o['end'] is None or dt<o['end'])]
 if len(valid)>1:
  return {**base,'status':'pending','records':_views([o['out'] for o in valid if o['out']],snap['changes']),'reason':'同一日期与号段落在多段沿革上，号段重叠，留待核定'}
 if not valid:
  mine=[o for o in occs if o['name']==old_name]
  if not mine:return {**base,'status':'none','records':[],'reason':'沿革簿没有该旧名的适用号段'}
  spans='、'.join(f"{o['start'].isoformat() if o['start'] else '记录起点'}～{o['end'].isoformat() if o['end'] else '现在'}" for o in mine)
  return {**base,'status':'pending','records':_views([o['out'] for o in mine if o['out']],snap['changes']),
          'reason':f'书证日期 {dated} 不在旧名 {old_name} 的有效期内（{spans}），无法确认所指旧路，留待核定'}
 occ=valid[0];used=[];cur=occ
 while cur and cur['next'] is not None:
  used.append(cur['out']);cur=cur['next']
 if not used:
  return {**base,'status':'none','records':[],'reason':f'书证 {dated} 时该路名下已是现名 {cur["name"]}，没有旧路可追认'}
 return {**base,'status':'traced','current_name':cur['name'],'records':_views(used,snap['changes']),
         'reason':f'书证 {dated}、门牌 {number_} 号沿 {len(used)} 段沿革记录追认至现名 {cur["name"]}'}

def _alias_attribution(snap,alias,entrance_number,evidence):
 num=number(alias['text']) or entrance_number
 hits=[x for x in snap['old_names'] if x in alias['text']]
 base={'alias_id':alias['id'],'text':alias['text'],'number':num}
 if not hits:return {**base,'status':'none'}
 longest=max(len(x) for x in hits);top=sorted({x for x in hits if len(x)==longest})
 if len(top)>1:return {**base,'status':'pending','reason':'别名同时包含多个路名，无法确定沿革，留待核定','records':[],'traces':[],'evidence':[]}
 old_name=top[0];base['old_name']=old_name
 evs=[x for x in evidence if x['alias_id']==alias['id']]
 evinfo=[{'id':x['id'],'reference':x['reference'],'dated':x['dated']} for x in evs]
 if not evs:return {**base,'status':'pending','reason':'该旧名别名没有书证，无法核对日期与号段，留待核定','evidence':[],'records':[],'traces':[]}
 traces=[trace_segments(snap,old_name,num,x['dated']) for x in evs]
 done=[x for x in traces if x['status']=='traced']
 if len({x['current_name'] for x in done})>1:
  return {**base,'status':'pending','reason':'多份书证追认到不同现路，归属不清，留待核定','evidence':evinfo,'traces':traces,'records':[]}
 wait=[x for x in traces if x['status']=='pending']
 if wait:
  return {**base,'status':'pending','reason':wait[0]['reason'],'evidence':evinfo,'traces':traces,'records':wait[0]['records']}
 if done:
  return {**base,'status':'traced','current_name':done[0]['current_name'],'evidence':evinfo,'traces':traces,'records':done[0]['records'],'reason':done[0]['reason']}
 return {**base,'status':'none','evidence':evinfo,'traces':traces,'records':[]}

def current_street(snap,street,number_):
 """入口登记街道若沿用旧名，沿号段沿革找到现名；无法判断时返回原名。"""
 segs=_component([g for g in snap['segments'] if _covers(g,number_)],street)
 if not segs:return street
 occs,err=_timeline(segs)
 if err or not occs:return street
 mine=[o for o in occs if o['name']==street]
 if not mine:return street
 cur=mine[-1]
 while cur['next'] is not None:cur=cur['next']
 return cur['name']

def entrance_attribution(snap,entrance,aliases,evidence):
 items=[_alias_attribution(snap,a,entrance['number'],evidence) for a in aliases if a['entrance_id']==entrance['id']]
 traced=[x for x in items if x['status']=='traced']
 pending=[x for x in items if x['status']=='pending']
 now=current_street(snap,entrance['street'],entrance['number'])
 status='traced' if traced else ('pending' if pending else 'none');reason=''
 off=[x for x in traced if x.get('current_name') and x['current_name']!=now]
 if traced and off:
  status='pending'
  reason=f"书证旧名 {off[0].get('old_name')} 追认现路为 {off[0]['current_name']}，与登记街道 {entrance['street']} 的现名 {now} 不一致，归属留待核定"
 elif traced and len({x['current_name'] for x in traced})>1:status='pending';reason='多个旧名别名追认到不同现路，归属不清，留待核定'
 elif pending:status='pending';reason=pending[0]['reason']
 out={'entrance_id':entrance['id'],'street':entrance['street'],'current_street':now,'number':entrance['number'],'status':status,'reason':reason,'items':items}
 out['fingerprint']=fingerprint(out)
 return out

def fingerprint(attr):
 def fact(x):
  recs=sorted((r['segment_id'],r['revision'],r['change_code']) for r in x.get('records') or [])
  return [x.get('old_name',''),x['number'],x['status'],x.get('current_name',''),recs]
 facts=sorted(fact(x) for x in attr['items'] if x['status']!='none')
 return hashlib.sha256(json.dumps({'entrance':attr['entrance_id'],'street':attr['street'],'current_street':attr.get('current_street'),'number':attr['number'],'facts':facts},ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def attribution(s,entrance_id,aliases=None,evidence=None):
 snap=snapshot(s)
 aliases=aliases if aliases is not None else [dump(x) for x in rows(s,Alias)]
 evidence=evidence if evidence is not None else [dump(x) for x in rows(s,Evidence)]
 return entrance_attribution(snap,dump(get(s,Entrance,entrance_id)),aliases,evidence)

def traced_names(attr):return sorted({x['current_name'] for x in attr['items'] if x['status']=='traced'})

def linked(x,y,ax,ay):
 """同号入口是否可沿现有记录归并：现路相同，或沿革书证把两边追认到同一现路。"""
 if x['number']!=y['number']:return False
 sx,sy=ax.get('current_street') or x['street'],ay.get('current_street') or y['street']
 if sx==sy:return True
 tx,ty=set(ax.get('traced_names') or []),set(ay.get('traced_names') or [])
 return bool(tx&ty) or sx in ty or sy in tx

def _validate(d):
 segs=d['segments']
 if not segs:fail('至少登记一个号段')
 names={x['new_name'] for x in segs};old={x['old_name'] for x in segs}
 if d['kind']=='rename' and len(names)!=1:fail('改名须只有一个新路名；多路名请选择拆分')
 if d['kind']=='split' and len(names)<2:fail('拆分至少产生两个新路名')
 if d['kind']=='split' and len(old)!=1:fail('拆分须来自同一个旧路名')
 seen=set()
 for x in segs:
  if x['old_name']==x['new_name']:fail('新旧路名不能相同')
  if x['from_number']>x['to_number']:fail('号段起号不得大于止号')
  day(x['effective'])
  k=(x['old_name'],x['new_name'],x['from_number'],x['to_number'],x['effective'])
  if k in seen:fail('同一号段重复登记，请核对')
  seen.add(k)

def register(s,d,u):
 r=lock(s);_validate(d)
 if s.scalars(select(RoadChange).where(RoadChange.code==d['code'])).first():fail('道路沿革编号已存在')
 x=RoadChange(code=d['code'],kind=d['kind'],reason=d['reason'],created=r.now,revision=1,state='active');s.add(x);s.flush()
 for g in d['segments']:s.add(RoadSegment(change_id=x.id,revision=1,**g))
 r.road_revision=(r.road_revision or 0)+1
 s.flush();return x

def correct(s,id,d,u):
 r=lock(s);x=get(s,RoadChange,id)
 _validate({'kind':x.kind,'segments':d['segments']})
 segs=[dump(g) for g in rows(s,RoadSegment) if g.change_id==x.id]
 s.add(RoadChangeHistory(change_id=x.id,revision=x.revision,snapshot={'change':dump(x),'segments':segs},reason=d['reason'],actor=u['email'],created=r.now))
 for g in rows(s,RoadSegment):
  if g.change_id==x.id:g.state='void'
 x.revision+=1;x.state='corrected';x.reason=d['reason']
 for g in d['segments']:s.add(RoadSegment(change_id=x.id,revision=x.revision,**g))
 r.road_revision=(r.road_revision or 0)+1
 s.flush()
 invalidate_public_notices(s,[x.id],'沿革记录已更正，公示依据需重新核定')
 return x

def basis(s,source_id,target_id):
 """把提案两侧入口当前的登记与沿革依据整理成可固化的公示依据。"""
 aliases=[dump(x) for x in rows(s,Alias)];evidence=[dump(x) for x in rows(s,Evidence)];snap=snapshot(s)
 cur={};recheck=[]
 for eid in (source_id,target_id):
  e=get(s,Entrance,eid);a=entrance_attribution(snap,dump(e),aliases,evidence)
  cur[eid]={'street':e.street,'number':e.number,'fingerprint':a['fingerprint'],
   'items':[{'old_name':x.get('old_name',''),'status':x['status'],'current_name':x.get('current_name',''),
             'records':[{'segment_id':r['segment_id'],'change_id':r['change_id'],'change_code':r['change_code'],'revision':r['revision'],
                         'old_name':r['old_name'],'new_name':r['new_name'],'from_number':r['from_number'],'to_number':r['to_number'],'effective':r['effective']} for r in x.get('records',[])]}
            for x in a['items'] if x['status']!='none']}
  if a['status']=='pending':recheck.append(f'入口 {e.code} 旧路归属待核定：{a["reason"]}')
 return {'source_id':source_id,'target_id':target_id,'entrances':cur,'recheck':sorted(set(recheck))}

def invalidate_public_notices(s,change_ids,reason):
 """沿革更正后，依据引用到被更正号段或归属指纹已变的待生效公示立即退回。
 原公示保留原 source/target 与原始依据，从不改指另一处。"""
 hit=set(change_ids);out=[]
 for n in rows(s,Notice):
  if n.state!='public':continue
  p=get(s,Proposal,n.proposal_id)
  refs={r.get('change_id') for v in (n.basis or {}).get('entrances',{}).values() for t in v.get('items',[]) for r in (t.get('records') or [])}
  fresh=basis(s,p.source_id,p.target_id);old=(n.basis or {}).get('entrances',{});moved=[]
  for eid,v in fresh['entrances'].items():
   prev=old.get(str(eid)) or old.get(eid)
   if not prev or prev.get('fingerprint')!=v['fingerprint'] or prev.get('street')!=v['street'] or prev.get('number')!=v['number']:
    moved.append(get(s,Entrance,eid).code if s.get(Entrance,eid) else str(eid))
  if refs&hit or moved or n.source_id!=p.source_id or n.target_id!=p.target_id:
   n.state='returned';n.returned_reason=reason+(f"（{'、'.join(moved)}）" if moved else '')
   p.state='returned';p.returned_reason=n.returned_reason;out.append(n)
 return out

def ledger(s):
 changes=rows(s,RoadChange);segs=rows(s,RoadSegment);hists=rows(s,RoadChangeHistory)
 out=[]
 for c in changes:
  mine=[dump(g) for g in segs if g.change_id==c.id];active=[g for g in mine if g['state']=='active'];warnings=[]
  for i,g in enumerate(active):
   for h in active[i+1:]:
    if g['old_name']==h['old_name'] and g['effective']==h['effective'] and g['from_number']<=h['to_number'] and h['from_number']<=g['to_number'] and g['new_name']!=h['new_name']:
     warnings.append(f"号段 {g['from_number']}-{g['to_number']} 与 {h['from_number']}-{h['to_number']} 同日重叠，匹配留待核定")
  if not active:warnings.append('没有生效号段，需更正后使用')
  out.append({**dump(c),'segments':mine,'history':[dump(h) for h in hists if h.change_id==c.id],'warnings':sorted(set(warnings))})
 return out
