from dataclasses import dataclass as _dc, asdict as _asdict, field as _field
import yaml as _yaml
from pathlib import Path as _Path
from typing import Literal as _Lit
import random as _RND

from .vehicles import IParams as _IP, VParams as _VP
from .persons import PersonParams as _PP

# default generation params
DEF_MIN_RTLEN = 10
DEF_MAX_RTLEN = 20
DEF_MIN_WALKLEN = 2
DEF_MAX_WALKLEN = 8
DEF_VNUM = 100
DEF_PNUM = 0
# DEF_TDEV_PROP = 0.1
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


def _normalize_dict(ld:list[dict]):
    if len(ld)==0:
        ld.append(dict())
        ld[0]["p"] = 1.0
        ld[0]["name"] = "DEFAULT"
        return
            
    totalp = sum([e.get("p",0.0) for e in ld])
    for i in range(len(ld)):
        dtmp = ld[i].copy()
        del dtmp["p"]
        del dtmp["name"]
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
class VehicleDrawMethod:
    name: _Lit["Uniform","TimeMovingGaussian","FixedAbsGaussian"] = "Uniform"
    tdevprop: float|None = None  # only for gaussians
    onBorders: _Lit["Clamp", "Redistribute"] = "Redistribute"  # only for gaussians
    sigmaScaling: _Lit["None","Triangular","Quadratic"]|None = None  # only for TimeMovingGaussian

    def correctBounds(self,val:float, minVal:float, maxVal:float)->float:
        match self.onBorders:
            case "Clamp":
                return max(minVal, min(maxVal, val))
            case "Redistribute":
                return val if minVal <= val <= maxVal else _RND.uniform(minVal, maxVal)
            case _:
                raise ValueError(f"Unknown VehicleDrawMethod onBorders: {self.onBorders}")
    
    def getSigmaScalingFactor(self,idx:int,total:int)->float:
        match self.sigmaScaling:
            case "Triangular":
                return 1 - abs(2*idx/total - 1)
            case "Quadratic":
                return (1 - abs(2*idx/total - 1))**2
            case _:
                return 1.0

    def generateDepartures(self,vnum:int,tot_sim_time:int,*,shuffle:bool=True)->list[float]:
        match self.name:
            case "Uniform":
                dpts = [_RND.uniform(0.0,tot_sim_time) for _ in range(vnum)]
            case "FixedAbsGaussian":
                sigma = tot_sim_time * self.tdevprop
                dpts = [self.correctBounds(abs(_RND.gauss(0, sigma)), 0.0, tot_sim_time) for _ in range(vnum)]
            case "TimeMovingGaussian":
                sigma = tot_sim_time * self.tdevprop
                mean_interval = tot_sim_time / vnum
                dpts = [self.correctBounds(_RND.gauss(i * mean_interval, sigma * self.getSigmaScalingFactor(i,vnum)), 0.0, tot_sim_time) for i in range(vnum)]
            case _:
                raise ValueError(f"Unknown VehicleDrawMethod name: {self.name}")
        
        if shuffle:
            _RND.shuffle(dpts)
        else:
            dpts.sort()
        return dpts
        

@_dc
class GenOptions:
    time: int = None
    split: bool = False
    steplen: float = None
    nroutes: int = None
    nwalks: int = None
    minrtlen: int = DEF_MIN_RTLEN
    maxrtlen: int = DEF_MAX_RTLEN
    minwalklen: int = DEF_MIN_WALKLEN
    maxwalklen: int = DEF_MAX_WALKLEN
    vnum: int = DEF_VNUM
    pnum: int = DEF_PNUM
    obstacles: int = DEF_OBSTACLES

    source_edges: list[str] = _field(default_factory=list)
    
    VehicleParams: list[dict] = _field(default_factory=list)
    IndividualParams: list[dict] = _field(default_factory=list)
    ClassParams: list[dict] = _field(default_factory=list)
    Modifiers: list[dict] = _field(default_factory=list)
    PersonParams: list[dict] = _field(default_factory=list)

    vDrawMethod: dict = _field(default_factory=dict)

    def copy(self,*,divide_by:int=None)->'GenOptions':
        gopts = GenOptions(**_asdict(self))
        if divide_by is not None:
            gopts.time = gopts.time // divide_by
            gopts.vnum = gopts.vnum // divide_by
            gopts.nroutes = gopts.nroutes // divide_by
            gopts.pnum = gopts.pnum // divide_by
            gopts.nwalks = gopts.nwalks // divide_by
            gopts.obstacles = gopts.obstacles // divide_by
        return gopts


    @staticmethod
    def fromYaml(yaml_path:_Path)->'GenOptions':
        gopts = GenOptions()
        gopts.loadYaml(yaml_path)
        return gopts
    
    def normalizeNullish(self):
        if self.nroutes is None:
            self.nroutes = self.vnum + self.obstacles
        if self.nwalks is None:
            self.nwalks = self.pnum
    
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

        _normalize_dict(self.VehicleParams)
        _normalize_dict(self.IndividualParams)
        _normalize_dict(self.ClassParams) # to be done
        _normalize_dict(self.PersonParams)
    
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
    def ModDict(self)->dict:
        return _ld_to_dt(self.Modifiers,dict)
    def VDrawMethod(self)->VehicleDrawMethod:
        return VehicleDrawMethod(**self.vDrawMethod)

    def print(self):
        print("Generation Options:")
        _printFormatted(_asdict(self),indent=0)

__all__ = ["GenOptions"]