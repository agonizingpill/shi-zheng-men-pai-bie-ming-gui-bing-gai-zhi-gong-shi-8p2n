import hashlib,json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import precision_score,recall_score
from sklearn.model_selection import train_test_split
from .numbers import number,normalize
# Simulated labelled historical alias pairs. Split before TFIDF fit/threshold selection.
def evaluation():
 pairs=[]
 for street in ['长桥路','青石街','河滨路','新民巷','榕树街','学府路','东湖路','西堤路','南苑街','北园街','柳岸路','梅花巷']:
  pairs.extend([(street+'18号',street+'十八号',1),(street+'18号南入口',street+'十八号南门',1),(street+'18号',street+'81号',0),(street+'18号',street+'19号',0)])
 tr,te=train_test_split(list(range(len(pairs))),test_size=.25,stratify=[x[2] for x in pairs],random_state=42)
 vec=TfidfVectorizer(analyzer='char',ngram_range=(1,3));vec.fit([normalize(t) for i in tr for t in pairs[i][:2]])
 def pred(ids,threshold):
  out=[]
  for i in ids:
   a,b,_=pairs[i];v=vec.transform([normalize(a),normalize(b)]);sim=float((v[0]@v[1].T).toarray()[0,0]);out.append(int(number(a)==number(b) and sim>=threshold))
  return out
 threshold=max([.35,.45,.55,.65,.75],key=lambda z:(precision_score([pairs[i][2] for i in tr],pred(tr,z),zero_division=0)+recall_score([pairs[i][2] for i in tr],pred(tr,z),zero_division=0),z))
 y=[pairs[i][2] for i in te];pr=pred(te,threshold)
 return {'seed':42,'train_pairs':len(tr),'holdout_pairs':len(te),'train_ids':tr,'holdout_ids':te,'precision':precision_score(y,pr,zero_division=0),'recall':recall_score(y,pr,zero_division=0),'threshold':threshold,'label_source':'模拟历史别名对；不代表真实地址精度'}
def _dist(sim):
 dist=np.clip(1-sim,0,2);np.fill_diagonal(dist,0);return dist
def _summary(attr):
 return {'status':attr['status'],'reason':attr['reason'],'fingerprint':attr['fingerprint'],'current_street':attr.get('current_street'),'street':attr['street'],'number':attr['number'],'entrance_id':attr['entrance_id'],
         'traced_names':sorted({x['current_name'] for x in attr['items'] if x['status']=='traced'}),
         'items':[{'alias_id':x['alias_id'],'text':x['text'],'old_name':x.get('old_name',''),'status':x['status'],'current_name':x.get('current_name',''),'reason':x.get('reason',''),'records':x.get('records',[])} for x in attr['items'] if x['status']!='none']}
def _records(attr):
 out=[]
 for x in attr['items']:
  for r in x.get('records',[]):out.append({**r,'alias_id':x['alias_id'],'old_name':x.get('old_name','')})
 return out
def match(entrances,aliases,evidence=None,road_snapshot=None,attribution_fn=None):
 if len(entrances)<2 or len(aliases)<2:raise ValueError('至少两个入口和两个有文字的别名')
 evidence=evidence or [];road_snapshot=road_snapshot or {'changes':{},'segments':[],'names':set(),'old_names':set()}
 texts=[normalize(a['text']) for a in aliases];vec=TfidfVectorizer(analyzer='char',ngram_range=(1,3));v=vec.fit_transform(texts);sim=(v@v.T).toarray()
 labels=AgglomerativeClustering(n_clusters=None,distance_threshold=.55,metric='precomputed',linkage='average').fit_predict(_dist(sim))
 eval=evaluation();candidates=[];by={x['id']:x for x in entrances}
 attr={x['id']:attribution_fn(road_snapshot,x,aliases,evidence) for x in entrances} if attribution_fn else {}
 for i,x in enumerate(entrances):
  for y in entrances[i+1:]:
   ix=[j for j,a in enumerate(aliases) if a['entrance_id']==x['id']];iy=[j for j,a in enumerate(aliases) if a['entrance_id']==y['id']]
   if not ix or not iy:continue
   pick=max(((sim[a,b],a,b) for a in ix for b in iy),key=lambda z:z[0]);score=float(pick[0])
   conflict=x['number']!=y['number'] or x['street']!=y['street']
   if score<.2:continue
   ax,ay=attr.get(x['id']),attr.get(y['id']);reasons=[];pending=False;road=False
   if ax and ay:
    for a in (ax,ay):
     if a['status']=='pending':
      pending=True
      if a['reason'] not in reasons:reasons.append(a['reason'])
    sx,sy=ax.get('current_street') or x['street'],ay.get('current_street') or y['street']
    tx,ty=set(ax.get('traced_names') or []),set(ay.get('traced_names') or [])
    if sx==sy or tx&ty or sx in ty or sy in tx:road=True
   state='pending' if pending else 'ranked'
   basis={'source':_summary(ax) if ax else None,'target':_summary(ay) if ay else None,
          'records':(_records(ax) if ax else [])+(_records(ay) if ay else []),
          'alias_pair':{'source_alias_id':aliases[pick[1]]['id'],'target_alias_id':aliases[pick[2]]['id'],'source_text':aliases[pick[1]]['text'],'target_text':aliases[pick[2]]['text']},
          'road_agreement':road}
   candidates.append({'source_id':x['id'],'target_id':y['id'],'similarity':round(score,6),'conflict':int(conflict),
                      'state':state,'reason':('；'.join(reasons))[:500],'basis':basis})
 candidates.sort(key=lambda c:(0 if c['state']=='ranked' else 1,-c['similarity'],c['source_id'],c['target_id']))
 for i,c in enumerate(candidates):c['rank']=i+1
 return {'algorithm':'道路沿革书证追认 + 字符TF-IDF+AgglomerativeClustering average linkage','source_sha256':hashlib.sha256(json.dumps([entrances,aliases,evidence],ensure_ascii=False,sort_keys=True).encode()).hexdigest(),'evaluation':eval,'clusters':[{'alias_id':a['id'],'label':int(k)} for a,k in zip(aliases,labels)],'attribution':[_summary(a) | {'entrance_id':k,'street':by[k]['street'],'number':by[k]['number']} for k,a in attr.items()],'candidates':candidates}
