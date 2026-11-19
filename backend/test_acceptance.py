"""道路沿革与归并核验的端到端验证。

运行：DATABASE_URL=sqlite:///… REDIS_URL=redis://127.0.0.1:1/0 python3 -m pytest test_acceptance.py -q
队列不可达时会自动退回进程内计算，正好用于无 Redis 的验收。
"""
import os,sys,tempfile
os.environ.setdefault('DATABASE_URL','sqlite:///'+tempfile.mkdtemp()+'/accept.db')
os.environ.setdefault('REDIS_URL','redis://127.0.0.1:1/0')
os.environ.setdefault('JWT_SECRET','acceptance-secret')
sys.path.insert(0,'/workspace/backend')
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.database import Session
from src.models import *
from src import road_service as road

@pytest.fixture(scope='module')
def c():
 with TestClient(app) as client:yield client

def login(c,role):
 r=c.post('/auth/login',json={'email':role+'@changqiao.local','password':'Address2026!'});assert r.status_code==200,r.text
 return {'Authorization':'Bearer '+r.json()['token']}

def ok(r,code=200):
 assert r.status_code==code,(r.status_code,r.text)
 return r.json()

def state():
 with Session() as s:return {k:[x for x in s.query(v).order_by(v.id)] for k,v in [('entrances',Entrance),('aliases',Alias),('evidence',Evidence),('proposals',Proposal),('notices',Notice),('redirects',Redirect),('objections',Objection)]}

# ---------- 1 道路改名/拆分登记：日期与号段、更正留版本 ----------
def test_register_rename_and_split_with_ranges(c):
 sup=login(c,'supervisor');op=login(c,'operator')
 r=ok(c.post('/roads',headers=op,json={'code':'T-RN','kind':'rename','reason':'试验路改名，按号段登记生效日','segments':[
   {'old_name':'试验旧路','new_name':'试验新路','from_number':1,'to_number':50,'effective':'2019-05-01'},
   {'old_name':'试验旧路','new_name':'试验新路','from_number':51,'to_number':120,'effective':'2019-05-01'}]}))
 assert r['kind']=='rename' and r['revision']==1
 ok(c.post('/roads',headers=op,json={'code':'T-SP','kind':'split','reason':'试验路北段拆分，按号段登记','segments':[
   {'old_name':'试验新路','new_name':'试验北路','from_number':51,'to_number':120,'effective':'2022-08-01'}]}),409)  # 拆分至少两个新名
 r=ok(c.post('/roads',headers=op,json={'code':'T-SP','kind':'split','reason':'试验路北段拆分，按号段登记','segments':[
   {'old_name':'试验新路','new_name':'试验东段','from_number':1,'to_number':50,'effective':'2022-08-01'},
   {'old_name':'试验新路','new_name':'试验北路','from_number':51,'to_number':120,'effective':'2022-08-01'}]}))
 assert r['kind']=='split'
 # 更正：留历史版本并递增 revision
 fixed=ok(c.post(f"/roads/{r['id']}/correct",headers=sup,json={'reason':'核对地籍图后更正北段止号','segments':[
   {'old_name':'试验新路','new_name':'试验东段','from_number':1,'to_number':50,'effective':'2022-08-01'},
   {'old_name':'试验新路','new_name':'试验北路','from_number':51,'to_number':130,'effective':'2022-08-01'}]}))
 assert fixed['revision']==2
 led=ok(c.get('/roads',headers=sup));sp=[x for x in led if x['code']=='T-SP'][0]
 assert len(sp['history'])==1 and any(g['state']=='void' for g in sp['segments'])
 assert len([g for g in sp['segments'] if g['state']=='active'])==2
 # 查阅员不可写
 ok(c.post('/roads',headers=login(c,'viewer'),json={'code':'T-X','kind':'rename','reason':'查阅员不可写：测试','segments':[{'old_name':'甲路','new_name':'乙路','from_number':1,'to_number':2,'effective':'2020-01-01'}]}),403)

# ---------- 2 逐段追认：按书证日期与门牌号 ----------
def test_trace_by_date_and_number(c):
 op=login(c,'operator')
 t=ok(c.get('/roads/trace',headers=op,params={'old_name':'试验旧路','number':30,'dated':'2018-01-01'}))
 assert t['status']=='traced' and t['current_name']=='试验东段',t
 assert [r['change_code'] for r in t['records']]==['T-RN','T-SP']
 t=ok(c.get('/roads/trace',headers=op,params={'old_name':'试验旧路','number':80,'dated':'2018-01-01'}))
 assert t['current_name']=='试验北路'
 t=ok(c.get('/roads/trace',headers=op,params={'old_name':'试验旧路','number':30,'dated':'2021-01-01'}))
 assert t['status']=='pending' and '有效期' in t['reason'],t
 t=ok(c.get('/roads/trace',headers=op,params={'old_name':'试验旧路','number':30}))
 assert t['status']=='pending' and '缺少日期' in t['reason']
 t=ok(c.get('/roads/trace',headers=op,params={'old_name':'试验新路','number':30,'dated':'2020-01-01'}))
 assert t['status']=='traced' and t['current_name']=='试验东段',t

# ---------- 3 重叠号段 / 缺日期分不清 -> 留待核定，不排序进候选 ----------
def test_overlap_and_missing_date_pend(c):
 sup=login(c,'supervisor');op=login(c,'operator')
 ok(c.post('/roads',headers=op,json={'code':'T-OV','kind':'split','reason':'同日重叠号段试验','segments':[
   {'old_name':'重叠旧巷','new_name':'重叠甲巷','from_number':1,'to_number':20,'effective':'2021-01-01'},
   {'old_name':'重叠旧巷','new_name':'重叠乙巷','from_number':10,'to_number':30,'effective':'2021-01-01'}]}))
 led=ok(c.get('/roads',headers=sup));ov=[x for x in led if x['code']=='T-OV'][0]
 assert ov['warnings'],'重叠号段应立即提示'
 t=ok(c.get('/roads/trace',headers=op,params={'old_name':'重叠旧巷','number':15,'dated':'2021-06-01'}))
 assert t['status']=='pending' and '重叠' in t['reason']
 # 两个入口使用重叠旧名 + 一个缺日期书证，匹配候选应为 pending 且无法形成提案
 e1=ok(c.post('/entrances',headers=op,json={'code':'T-OV-A','street':'重叠甲巷','number':15,'label':'重叠甲巷15号东门','lat':31.2,'lng':121.5}))
 e2=ok(c.post('/entrances',headers=op,json={'code':'T-OV-B','street':'重叠乙巷','number':15,'label':'重叠乙巷15号西门','lat':31.2001,'lng':121.5}))
 a1=ok(c.post('/aliases',headers=op,json={'entrance_id':e1['id'],'text':'重叠旧巷15号东门'}))
 a2=ok(c.post('/aliases',headers=op,json={'entrance_id':e2['id'],'text':'重叠旧巷15号西门'}))
 ok(c.post('/evidence',headers=op,json={'alias_id':a1['id'],'reference':'T-OV-证1','description':'重叠号段书证，应留待核定','dated':'2021-06-01'}))
 ok(c.post('/evidence',headers=op,json={'alias_id':a2['id'],'reference':'T-OV-证2','description':'缺日期书证，应留待核定'}))
 ok(c.post('/matches',headers=op))
 with Session() as s:
  cs=[x for x in s.query(Candidate).filter(Candidate.source_id.in_([e1['id'],e2['id']]),Candidate.target_id.in_([e1['id'],e2['id']]))]
  assert cs and all(x.state=='pending' and x.rank>0 for x in cs),[ (x.state,x.reason) for x in cs]
  cid=cs[0].id
 r=c.post('/proposals',headers=op,json={'code':'T-OV-P','source_id':cs[0].source_id,'target_id':cs[0].target_id,'reason':'沿革待核定不该能提案','candidate_id':cid})
 assert r.status_code==409 and '待核定' in r.json()['detail'],r.text

# ---------- 4 旧路名重用：先按书证日期和号段追认，再按别名相似度排候选 ----------
def test_reuse_ranking(c):
 op=login(c,'operator')
 # 试验东段 于 2024 改回旧名 试验旧路（1-50），旧名被重新使用
 ok(c.post('/roads',headers=op,json={'code':'T-RU','kind':'rename','reason':'试验东段重新启用旧名，验证重用','segments':[
   {'old_name':'试验东段','new_name':'试验旧路','from_number':1,'to_number':50,'effective':'2024-01-01'}]}))
 # 书证在 2019 之前：沿同一条路的完整沿革链追认，包含 2024 年改回旧名的一段
 t=ok(c.get('/roads/trace',headers=op,params={'old_name':'试验旧路','number':30,'dated':'2018-01-01'}))
 assert t['status']=='traced' and t['current_name']=='试验旧路'
 assert [r['change_code'] for r in t['records']]==['T-RN','T-SP','T-RU']
 # 书证落在停用间隙（2019-05 至 2024-01）：名称已被重新使用，归属留待核定
 t=ok(c.get('/roads/trace',headers=op,params={'old_name':'试验旧路','number':30,'dated':'2023-06-01'}))
 assert t['status']=='pending' and '有效期' in t['reason'],t
 # 书证日期在重用之后：该名当时就是现名，没有旧路可追认，不能猜
 t=ok(c.get('/roads/trace',headers=op,params={'old_name':'试验旧路','number':30,'dated':'2025-01-01'}))
 assert t['status']=='none' and '现名' in t['reason'],t

def test_entrance_registered_under_old_name_can_merge(c):
 op=login(c,'operator');sup=login(c,'supervisor')
 # 入口登记用的是旧路名（2018），现路为 试验旧路；另一入口登记现路名，同号同位置
 old=ok(c.post('/entrances',headers=op,json={'code':'T-OLD-A','street':'试验旧路','number':40,'label':'旧名登记的正门','lat':31.23,'lng':121.46}))
 now=ok(c.post('/entrances',headers=op,json={'code':'T-OLD-B','street':'试验东段','number':40,'label':'现名登记的旧门','lat':31.2301,'lng':121.46}))
 f=ok(c.post('/proposals',headers=op,json={'code':'T-OLD','source_id':now['id'],'target_id':old['id'],'reason':'旧路名登记入口与现名入口号段追认到同一条路'}))
 assert f['state']=='draft'
 # 登记旧名且书证追认现路与登记现名一致：入口自身状态为 traced，不误报
 a=ok(c.get(f"/roads/attribution/{old['id']}",headers=op))
 assert a['current_street']=='试验旧路' and a['status'] in ('none','traced'),a

# ---------- 5 归并核验页面能看到候选沿用了哪些记录 ----------
def test_candidate_basis_records(c):
 op=login(c,'operator');sup=login(c,'supervisor')
 ok(c.post('/matches',headers=op))
 reg=ok(c.get('/register',headers=sup));run=reg['runs'][-1]
 cands=[x for x in reg['candidates'] if x['run_id']==run['id']]
 assert cands
 for x in cands:
  assert 'records' in x['basis'] and 'source' in x['basis'] and 'target' in x['basis']
 # 有沿革书证的候选必须列出实际沿用记录
 with Session() as s:
  seeded=[x for x in s.query(Candidate).filter(Candidate.basis.isnot(None))][-1]
  assert isinstance(seeded.basis.get('records'),list)
 # 候选复核：排除后不可再提案
 target=[x for x in cands if x['state']=='ranked'][0]
 r=ok(c.post(f"/candidates/{target['id']}/review",headers=op,json={'state':'rejected','note':'现场核对后排除该候选'}))
 assert r['state']=='rejected'
 p=c.post('/proposals',headers=op,json={'code':'T-REJ','source_id':target['source_id'],'target_id':target['target_id'],'reason':'排除的候选不得提案','candidate_id':target['id']})
 assert p.status_code==409
 # 未复核候选可形成提案并标 confirmed
 good=[x for x in cands if x['state']=='ranked' and not x['conflict'] and x['id']!=target['id']]
 assert good
 g=good[0]
 ok(c.post('/proposals',headers=op,json={'code':'T-CONF','source_id':g['source_id'],'target_id':g['target_id'],'reason':'候选沿革记录一致，可形成提案','candidate_id':g['id']}))
 with Session() as s:assert s.get(Candidate,g['id']).state=='confirmed'

# ---------- 6 改名更正与公示生效并发：归属变了的退回复核，原公示不被改指 ----------
def test_correction_during_publication_returns(c):
 sup=login(c,'supervisor');op=login(c,'operator')
 ent=ok(c.post('/entrances',headers=op,json={'code':'T-PUB-A','street':'并发街','number':7,'label':'并发街7号正门','lat':31.21,'lng':121.49}))
 tgt=ok(c.post('/entrances',headers=op,json={'code':'T-PUB-B','street':'并发街','number':7,'label':'并发街7号旧门','lat':31.2101,'lng':121.49}))
 al=ok(c.post('/aliases',headers=op,json={'entrance_id':ent['id'],'text':'改名作业街7号正门'}))
 ok(c.post('/evidence',headers=op,json={'alias_id':al['id'],'reference':'T-PUB-照','description':'公示前现场核验照片','dated':'2020-01-01'}))
 ok(c.post('/roads',headers=sup,json={'code':'T-PUB-RC','kind':'rename','reason':'并发改名，公示范畴依据','segments':[
   {'old_name':'改名作业街','new_name':'并发街','from_number':1,'to_number':99,'effective':'2020-06-01'}]}))
 p=ok(c.post('/proposals',headers=op,json={'code':'T-PUB','source_id':ent['id'],'target_id':tgt['id'],'reason':'同名同号，公示依据为改名沿革'}))
 n=ok(c.post('/notices',headers=sup,json={'proposal_id':p['id'],'days':3}))
 assert n['basis'] and str(ent['id']) in {str(k) for k in n['basis']['entrances']}
 ok(c.post('/clock',headers=sup,json={'now':'2026-11-25T09:00:00','reason':'模拟公示期满，进入生效核定'}))
 # 公示后、生效前更正改名沿革：把 7 号从改名链中移出（号段改为 20-99），归属变化
 ok(c.post(f"/roads/{[x for x in ok(c.get('/roads',headers=sup)) if x['code']=='T-PUB-RC'][0]['id']}/correct",headers=sup,json={
   'reason':'复核地籍图后更正号段，7号不在改名范围','segments':[{'old_name':'改名作业街','new_name':'并发街','from_number':20,'to_number':99,'effective':'2020-06-01'}]}))
 # 更正当刻即退回：不必等到点生效按钮
 reg=ok(c.get('/register',headers=sup))
 notice=[x for x in reg['notices'] if x['id']==n['id']][0]
 assert notice['state']=='returned' and notice['returned_reason'],notice
 assert notice['source_id']==ent['id'] and notice['target_id']==tgt['id'],'原公示必须保留原指向'
 assert notice['basis']['entrances'][str(ent['id'])]['street']=='并发街','原依据不得被改写'
 prop=[x for x in reg['proposals'] if x['id']==p['id']][0]
 assert prop['state']=='returned'
 r=ok(c.get('/returned',headers=sup))
 assert r and r[0]['notice_id']==n['id'] and r[0]['source_id']==ent['id']
 # 没有生成目录映射
 with Session() as s:assert not s.query(Redirect).filter(Redirect.proposal_id==p['id']).count()
 # 退回后原公示不能再点生效；也不会被改成别的指向
 e=c.post(f"/notices/{n['id']}/effective",headers=sup)
 assert e.status_code==409
 reg=ok(c.get('/register',headers=sup))
 again=[x for x in reg['notices'] if x['id']==n['id']][0]
 assert again['source_id']==ent['id'] and again['target_id']==tgt['id']
 # 拆分退回的提案，两个入口保留
 ok(c.post(f"/proposals/{p['id']}/split",headers=sup,json={'proposal_id':p['id'],'reason':'现场确认两个入口独立，拆分保留门牌'}))
 with Session() as s:
  assert s.get(Proposal,p['id']).state=='rejected'
  assert s.get(Entrance,ent['id']) and s.get(Entrance,tgt['id'])

# ---------- 7 正常路径仍要能生效并解析 ----------
def test_happy_effective_and_rollback(c):
 sup=login(c,'supervisor');op=login(c,'operator')
 ok(c.post('/roads',headers=sup,json={'code':'T-OK-RC','kind':'rename','reason':'正常改名，公示依据','segments':[
   {'old_name':'正常旧街','new_name':'正常街','from_number':1,'to_number':99,'effective':'2020-01-01'}]}))
 a=ok(c.post('/entrances',headers=op,json={'code':'T-OK-A','street':'正常街','number':9,'label':'正常街9号正门','lat':31.22,'lng':121.47}))
 b=ok(c.post('/entrances',headers=op,json={'code':'T-OK-B','street':'正常街','number':9,'label':'正常街9号旧门','lat':31.2201,'lng':121.47}))
 al=ok(c.post('/aliases',headers=op,json={'entrance_id':b['id'],'text':'正常旧街9号旧门'}))
 ok(c.post('/evidence',headers=op,json={'alias_id':al['id'],'reference':'T-OK-照','description':'正常路径现场核验照片','dated':'2019-01-01'}))
 p=ok(c.post('/proposals',headers=op,json={'code':'T-OK','source_id':b['id'],'target_id':a['id'],'reason':'旧名书证追认到同一现路'}))
 n=ok(c.post('/notices',headers=sup,json={'proposal_id':p['id'],'days':3}))
 ok(c.post('/clock',headers=sup,json={'now':'2026-12-05T09:00:00','reason':'推进时钟越过三日公示期限'}))
 r=ok(c.post(f"/notices/{n['id']}/effective",headers=sup))
 assert r['state']=='active'
 d=ok(c.get(f"/directory/{b['id']}",headers=op))
 assert d['canonical_id']==a['id'] and d['chain']==[b['id'],a['id']]
 ok(c.post(f"/redirects/{r['id']}/rollback",headers=sup,json={'reason':'复核发现旧入口独立，回滚映射保留记录'}))
 d=ok(c.get(f"/directory/{b['id']}",headers=op))
 assert d['canonical_id']==b['id']
