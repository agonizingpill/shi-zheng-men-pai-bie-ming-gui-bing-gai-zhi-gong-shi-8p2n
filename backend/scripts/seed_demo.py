from src.database import Session,Base,engine
from src.models import *
from src.security import password_hash
from src.common import rows

def seed():
 Base.metadata.create_all(engine)
 with Session() as s:
  for role in ['operator','supervisor','viewer']:
   if not any(x.email==role+'@changqiao.local' for x in rows(s,User)):s.add(User(email=role+'@changqiao.local',password=password_hash('Address2026!'),role=role))
  if not s.get(Registry,1):s.add(Registry(id=1,now='2026-11-18T09:00:00'))
  if not any(x.code=='CQ-018-A' for x in rows(s,Entrance)):
   for code,num,label,lat in [('CQ-018-A',18,'长桥路18号正门',31.210),('CQ-018-B',18,'长桥路十八号旧门牌',31.2101),('CQ-081',81,'长桥路81号',31.211),('CQ-018-C',18,'长桥路18号南入口',31.2102)]:
    e=Entrance(code=code,street='长桥路',number=num,label=label,lat=lat,lng=121.48);s.add(e);s.flush();a=Alias(entrance_id=e.id,text=label);s.add(a);s.flush();s.add(Evidence(alias_id=a.id,reference='照片-'+code,description='2026年11月现场门牌照片与老地籍图位置核验说明',dated='2026-11-18'))
   s.flush();es=rows(s,Entrance);p=Proposal(code='P031',source_id=es[1].id,target_id=es[0].id,reason='历史十八号门牌与现18号正门同宗同入口');s.add(p);s.flush();s.add(Objection(proposal_id=p.id,code='Y031',note='住户认为旧门牌对应独立南入口，申请现场复核',state='open'))
  if not any(x.code=='RC-001' for x in rows(s,RoadChange)):
   c=RoadChange(code='RC-001',kind='rename',reason='2021年市政道路改名备案，旧路名在新门牌启用后停用',created='2021-03-01',revision=1,state='active');s.add(c);s.flush()
   s.add(RoadSegment(change_id=c.id,old_name='长桥老街',new_name='长桥路',from_number=1,to_number=80,effective='2021-04-01',revision=1,state='active'))
  if not any(x.code=='RC-002' for x in rows(s,RoadChange)):
   c=RoadChange(code='RC-002',kind='split',reason='北段析出为青石街，按门牌号段登记新旧对照',created='2023-06-01',revision=1,state='active');s.add(c);s.flush()
   s.add(RoadSegment(change_id=c.id,old_name='长桥东段',new_name='长桥路',from_number=1,to_number=50,effective='2023-07-01',revision=1,state='active'))
   s.add(RoadSegment(change_id=c.id,old_name='长桥东段',new_name='青石街',from_number=51,to_number=120,effective='2023-07-01',revision=1,state='active'))
  s.commit()
if __name__=='__main__':seed()
