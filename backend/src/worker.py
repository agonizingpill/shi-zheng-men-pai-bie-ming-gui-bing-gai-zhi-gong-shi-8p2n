import os,time,pathlib,logging
import redis
from .database import Session
from .models import MatchRun,Entrance,Alias,Evidence,Candidate
from .common import lock,rows,dump
from .matching import match
from . import road_service as road
def process(s,run_id):
 run=s.get(MatchRun,int(run_id))
 if not run or run.state!='queued':return False
 try:
  result=match([dump(x) for x in rows(s,Entrance)],[dump(x) for x in rows(s,Alias)],[dump(x) for x in rows(s,Evidence)],road.snapshot(s),road.entrance_attribution)
  run.result=result
  snap=road.snapshot(s);snap['names']=sorted(snap['names']);snap['old_names']=sorted(snap['old_names']);snap['changes']={str(k):v for k,v in snap['changes'].items()};run.road_snapshot=snap
  for d in result['candidates']:s.add(Candidate(run_id=run.id,**d))
  run.state='ready'
 except Exception as e:
  run.state='failed';run.error=str(e)[:500];logging.exception('matching failed')
 return True
def main():
 q=redis.from_url(os.environ['REDIS_URL'],decode_responses=True)
 while True:
  pathlib.Path('/artifacts/address-heartbeat').write_text(str(time.time()))
  item=q.blpop('address:matching',timeout=2)
  if not item:continue
  with Session() as s:
   lock(s);process(s,item[1]);s.commit()
if __name__=='__main__':main()
