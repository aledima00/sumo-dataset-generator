from .labels import MultiLabel as _MLB
from dataclasses import dataclass as _dc, field as _field
from .vehicle import Vehicle as _Vehicle

@_dc
class Frame:
    vehicles: dict[str, _Vehicle] = _field(default_factory=dict)
    obstacles: dict[str, _Vehicle] = _field(default_factory=dict)
    
    def getVehsByLane(self, lane_id:str) -> list[_Vehicle]:
        vehs = self.vehicles.values()
        return [v for v in vehs if v.lane_id == lane_id]

class StaticPackAnalyzer:
    ml: _MLB
    frames_pack:list[Frame]

    def __init__(self, frames_pack:list[Frame],initML:_MLB=None):
        self.frames_pack = frames_pack
        self.ml = initML if initML is not None else _MLB()

    def analyze(self)->_MLB:
        return self.ml

__all__ = ['Edge','Frame', 'Pack', 'StaticPackAnalyzer']
