from dataclasses import dataclass as _dc, asdict as _asdict, field as _field
import yaml as _yaml
from pathlib import Path as _Path
from .vehicles import IParams as _IP, VParams as _VP
from .persons import PersonParams as _PP

# default generation params
DEF_N_WALKS = 20
DEF_MIN_RTLEN = 10
DEF_MAX_RTLEN = 20
DEF_MIN_WALKLEN = 2
DEF_MAX_WALKLEN = 8
DEF_VNUM = 100
DEF_PNUM = 50
DEF_TDEV_PROP = 0.1
DEF_OBSTACLES = 0

def _indp(strval:str,*,indnl:int,):
    return print(strval,end="\n"+"  " * indnl if indnl>=0 else "")

def _printFormatted(elm,indent:int=0):
    match type(elm).__name__:
        case 'dict':
            _indp("{",indnl=indent+1)
            for k,v in elm.items():
                _indp(f"{k}: ",indnl=-1)
                _printFormatted(v,indent=indent+1)
            _indp("}", indnl=indent)
        case 'list':
            _indp("[",indnl=indent+1)
            for i,v in enumerate(elm):
                _indp(f".{i}) ",indnl=-1)
                _printFormatted(v,indent=indent+1)
            _indp("]", indnl=indent)
        case _:
            _indp(f"{elm}", indnl=indent)

def _dc_or_dict_asdict(elm)->dict:
    return elm if type(elm) is dict else _asdict(elm)

def _normalize_dict(ld:list[dict],factory):
    if len(ld)==0:
        ld.append(_dc_or_dict_asdict(factory()))
        ld[0]["p"] = 1.0
        ld[0]["name"] = "DEFAULT"
        return
            
    totalp = sum([e.get("p",0.0) for e in ld])
    for i in range(len(ld)):
        dtmp = ld[i].copy()
        del dtmp["p"]
        del dtmp["name"]
        dtmp = factory(**dtmp)
        dtmp = _dc_or_dict_asdict(dtmp)
        dtmp["p"] = ld[i].get("p",0.0) / totalp if totalp > 0 else 0
        dtmp["name"] = ld[i].get("name")
        if dtmp["name"] is None:
            raise ValueError("Each dictionary entry must have a 'name' field.")
        ld[i] = dtmp

def _ld_to_dt(ld:list[dict],clout)->dict[tuple]:
    ret = dict()
    for e in ld:
        if clout == str:
            ret[e["name"]] = (e["p"], e["vClass"])
        else:
            content = e.copy()
            del content["name"]
            del content["p"]
            ret[e["name"]] = (e["p"], clout(**content))
    return ret

@_dc
class GenOptions:
    time: int = None
    steplen: float = None
    nroutes: int = None
    nwalks: int = DEF_N_WALKS
    minrtlen: int = DEF_MIN_RTLEN
    maxrtlen: int = DEF_MAX_RTLEN
    minwalklen: int = DEF_MIN_WALKLEN
    maxwalklen: int = DEF_MAX_WALKLEN
    vnum: int = DEF_VNUM
    pnum: int = DEF_PNUM
    tdevp: float = DEF_TDEV_PROP
    obstacles: int = DEF_OBSTACLES

    source_edges: list[str] = _field(default_factory=list)
    
    VehicleParams: list[dict] = _field(default_factory=list)
    IndividualParams: list[dict] = _field(default_factory=list)
    ClassParams: list[dict] = _field(default_factory=list)
    ProportionalModifiers: list[dict] = _field(default_factory=list)
    PersonParams: list[dict] = _field(default_factory=list)

    @staticmethod
    def fromYaml(yaml_path:_Path)->'GenOptions':
        gopts = GenOptions()
        gopts.loadYaml(yaml_path)
        return gopts
    
    def normalizeNullish(self):
        if self.nroutes is None:
            self.nroutes = self.vnum + self.obstacles
    
    def loadYaml(self,yaml_path:_Path):
        emptyyml:bool = False
        if (not yaml_path.exists()) or (not yaml_path.is_file()):
            #yaml_path.parent.mkdir(parents=True,exist_ok=True)
            #yaml_path.touch()
            emptyyml = True
        else:
            with open(yaml_path,'r') as yf:
                options_dict:dict = _yaml.safe_load(yf)
                if options_dict is None:
                    emptyyml = True

        if not emptyyml:        
            for k,v in options_dict.items():
                if not hasattr(self,k):
                    raise ValueError(f"Unknown generation option '{k}' in YAML file '{yaml_path}'")
                else:
                    setattr(self,k,v)

        _normalize_dict(self.VehicleParams, factory=_VP)
        _normalize_dict(self.IndividualParams,factory=_IP)
        _normalize_dict(self.ClassParams,factory=dict) # to be done
        _normalize_dict(self.PersonParams,factory=_PP)
    
    def dump(self,yaml_path:_Path):
        options_dict = _asdict(self)
        with open(yaml_path,'w') as yf:
            yf.write("---\n")
            for k,v in _asdict(self).items():
                if v is None:
                    del options_dict[k]
            _yaml.dump(options_dict,yf,default_flow_style=False,allow_unicode=True)

    def overwriteWith(self,**kwargs):
        for k,v in kwargs.items():
            if v is not None and (type(v) is not str or v != ''):
                setattr(self,k,v)

    def IPDict(self)->dict:
        return _ld_to_dt(self.IndividualParams,_IP)
    def VPDict(self)->dict:
        return _ld_to_dt(self.VehicleParams,_VP)
    def VCLDict(self)->dict:
        return _ld_to_dt(self.ClassParams,str)
    def PPDict(self)->dict:
        return _ld_to_dt(self.PersonParams,_PP)
    def PMDict(self)->dict:
        return _ld_to_dt(self.ProportionalModifiers,dict)

    def print(self):
        print("Generation Options:")
        _printFormatted(_asdict(self),indent=0)

__all__ = ["GenOptions"]