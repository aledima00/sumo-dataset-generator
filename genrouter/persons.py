from dataclasses import dataclass as _dc, asdict as _asdict, field as _field
from .graph import WalkRepresentation as _WKRepr
from .station import StationType as _ST

@_dc
class PersonParams:
    mingap: float = 0.25
    maxSpeed: float = 4.0  # m/s
    desiredMaxSpeed: float = 1.5
    speedDev: float = 0.1
    color: str = "0,0,1"
    jmDriveAfterRedTime: float = 0.0  # time in seconds to wait before crossing on red
    jmIgnoreFoeProb: float = 0.1  # probability [0-1] of ignoring foe vehicles that have right-of-way
    jmIgnoreFoeSpeed: float = 5.0  # in conjunction with jmIgnoreFoeProb - Only vehicles with a speed (m/s) below or equal to the given value may be ignored.
    impatience: float = 0.5  # Willingness [0-1] of persons to walk across the street at an unprioritized crossing when there are vehicles that would have to brake
    # other rarely used parameters are omitted for simplicity
    speedFactor: float = 1.0


@_dc
class PType:
    name: str
    pp: PersonParams = _field(default_factory=PersonParams)    

    @property
    def id(self) -> str:
        return f"ST{_ST.PEDESTRIAN.value:03d}_{self.name}"

    def xml(self) -> str:
        pp_attrs_str = ' '.join(f'{k}="{v}"' for k, v in _asdict(self.pp).items())
        return f'<vType id="{self.id}" {pp_attrs_str} vClass="pedestrian"/>'
    
    def __str__(self):
        return str(self.id)
    def __repr__(self):
        return str(self)
    def __hash__(self):
        return hash(self.id)
    def __eq__(self, other):
        return self.id == other.id

class Person:
    id: str
    depart_time: float
    walks: list[_WKRepr]
    def __init__(self,id:str,depart_time:float,ptype_id:str):
        self.id = id
        self.depart_time = depart_time
        self.walks = []
        self.ptype_id = ptype_id
    def addWalk(self, walk:_WKRepr):
        self.walks.append(walk)
    def xml(self,*,tabs=0)->str:
        x = f'{"\t"*tabs}<person type="{self.ptype_id}" id="{self.id}" depart="{self.depart_time}">\n'
        for w in self.walks:
            x += f'{"\t"*(tabs+1)}{w.xml()}\n'
        x += f'{"\t"*tabs}</person>'
        return x