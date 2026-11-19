from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
class Input(BaseModel):
 model_config=ConfigDict(extra='forbid',str_strip_whitespace=True,allow_inf_nan=False)
class Login(Input):
 email:str;password:str
class EntranceIn(Input):
 code:str=Field(min_length=2,max_length=40);street:str=Field(min_length=2,max_length=80);number:int=Field(ge=1,le=99999);label:str=Field(min_length=3,max_length=100);lat:float=Field(ge=-90,le=90);lng:float=Field(ge=-180,le=180)
class LocationIn(Input):
 lat:float=Field(ge=-90,le=90);lng:float=Field(ge=-180,le=180);reason:str=Field(min_length=8,max_length=400)
class AliasIn(Input):
 entrance_id:int;text:str=Field(min_length=3,max_length=120)
class ObjectionIn(Input):
 proposal_id:int;code:str=Field(min_length=2,max_length=40);note:str=Field(min_length=8,max_length=500)
class ResolveIn(Input):
 decision:Literal['uphold','split'];resolution:str=Field(min_length=8,max_length=500)
class NoticeIn(Input):
 proposal_id:int;days:int=Field(ge=3,le=30)
class ReasonIn(Input):
 reason:str=Field(min_length=8,max_length=500)
class ClockIn(Input):
 now:str;reason:str=Field(min_length=8,max_length=500)

class SegmentIn(Input):
 old_name:str=Field(min_length=2,max_length=80);new_name:str=Field(min_length=2,max_length=80);from_number:int=Field(ge=1,le=99999);to_number:int=Field(ge=1,le=99999);effective:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
class RoadChangeIn(Input):
 code:str=Field(min_length=2,max_length=40);kind:Literal['rename','split'];reason:str=Field(min_length=8,max_length=500);segments:list[SegmentIn]=Field(min_length=1,max_length=40)
class RoadCorrectIn(Input):
 reason:str=Field(min_length=8,max_length=500);segments:list[SegmentIn]=Field(min_length=1,max_length=40)
class EvidenceIn(Input):
 alias_id:int;reference:str=Field(min_length=3,max_length=100);description:str=Field(min_length=8,max_length=500);dated:str=Field(default='',pattern=r'^(\d{4}-\d{2}-\d{2})?$')
class ProposalIn(Input):
 code:str=Field(min_length=2,max_length=40);source_id:int;target_id:int;reason:str=Field(min_length=8,max_length=500);candidate_id:int|None=None
class CandidateReviewIn(Input):
 state:Literal['ranked','rejected'];note:str=Field(min_length=8,max_length=500)
class SplitIn(Input):
 proposal_id:int;reason:str=Field(min_length=8,max_length=500)

class TraceIn(Input):
 old_name:str=Field(min_length=2,max_length=80);number:int=Field(ge=1,le=99999);dated:str=Field(default='',pattern=r'^(\d{4}-\d{2}-\d{2})?$')
