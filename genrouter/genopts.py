from dataclasses import dataclass as _dc, asdict as _asdict, field as _field
import yaml as _yaml
from pathlib import Path as _Path
from .vehicles import IParams as _IP, VParams as _VP

# default generation params
DEF_N_ROUTES = 10
DEF_MIN_RTLEN = 10
DEF_MAX_RTLEN = 20
DEF_VNUM = 100
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

def _normalize_dict(ld:list[dict]):
    if ld is None:
        raise ValueError("List of dictionaries is None.")
    totalp = sum([e.get("p",0) for e in ld])
    for d in ld:
        d["p"] = d.get("p",0) / totalp if totalp > 0 else 0
        if d.get("name",None) is None:
            raise ValueError("Each dictionary entry must have a 'name' field.")

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
    nroutes: int = DEF_N_ROUTES
    minrtlen: int = DEF_MIN_RTLEN
    maxrtlen: int = DEF_MAX_RTLEN
    vnum: int = DEF_VNUM
    tdevp: float = DEF_TDEV_PROP
    obstacles: int = DEF_OBSTACLES

    VehicleParams: list[dict] = _field(default_factory=list)
    IndividualParams: list[dict] = _field(default_factory=list)
    ClassParams: list[dict] = _field(default_factory=list)
    ProportionalModifiers: list[dict] = _field(default_factory=list)

    @staticmethod
    def fromYaml(yaml_path:_Path)->'GenOptions':
        gopts = GenOptions()
        gopts.loadYaml(yaml_path)
        return gopts
    
    def loadYaml(self,yaml_path:_Path):
        if (not yaml_path.exists()) or (not yaml_path.is_file()):
            return
        with open(yaml_path,'r') as yf:
            options_dict:dict = _yaml.safe_load(yf)
        
        
        for k,v in options_dict.items():
            if not hasattr(self,k):
                raise ValueError(f"Unknown generation option '{k}' in YAML file '{yaml_path}'")
            elif type(v).__name__ != 'list':
                setattr(self,k,v)
            else:
                optl = options_dict.get(k,None)
                if optl is not None:
                    l:list[dict] = getattr(self,k)
                    l.clear()
                    for d in optl:
                        l.append(d.copy())

        _normalize_dict(self.VehicleParams)
        _normalize_dict(self.IndividualParams)
        _normalize_dict(self.ClassParams)
    
    def dump(self,yaml_path:_Path):
        options_dict = _asdict(self)
        with open(yaml_path,'w') as yf:
            yf.write("---\n")
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
    def PMDict(self)->dict:
        return _ld_to_dt(self.ProportionalModifiers,dict)

    def print(self):
        print("Generation Options:")
        _printFormatted(_asdict(self),indent=0)

__all__ = ["GenOptions"]