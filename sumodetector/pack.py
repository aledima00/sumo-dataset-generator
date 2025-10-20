from .labels import MultiLabel as _MLB, LabelsEnum as _LE
from dataclasses import dataclass as _dc, field as _field
from .vehicle import Vehicle as _Vehicle

@_dc
class Frame:
    vehicles: dict[str, _Vehicle] = _field(default_factory=dict)
    obstacles: dict[str, _Vehicle] = _field(default_factory=dict)


_DEF_BRAKING_THRESHOLD = -2.0 # m/s^2

@_dc
class LaneChange:
    id1:str
    id2:str

class StaticPackAnalyzer:
    ml: _MLB
    frames_pack:list[Frame]
    braking_threshold:float

    def __init__(self, frames_pack:list[Frame],initML:_MLB=None,braking_threshold = _DEF_BRAKING_THRESHOLD):
        self.frames_pack = frames_pack
        self.ml = _MLB() if initML is None else initML
        self.braking_threshold = braking_threshold

    def __checkBraking(self)->bool:
        for frame in self.frames_pack:
            # cycle over vehicles in frame
            for vid,v in frame.vehicles.items():

                if v.acceleration < self.braking_threshold:
                    self.ml.setLabel(_LE.BRAKING)
                    return

    def __checkLaneChangeMerge(self)->bool:
        for fnum,frame in enumerate(self.frames_pack):
            if fnum==0:
                continue
            for vid,v in frame.vehicles.items():
                vprev = self.frames_pack[fnum-1].vehicles.get(vid,None)
                if vprev is not None and v.lane_id != vprev.lane_id:
                    # generic lane change situation
                    self.ml.setLabel(_LE.LANE_CHANGE)
                    return # early exit, but may be replaced by check for lane merge

    def __checkObstacle(self):
        for frame in self.frames_pack:
            if len(frame.obstacles)>0:
                self.ml.setLabel(_LE.OBSTACLE_IN_ROAD)
                return

    def analyze(self)->_MLB:
        self.__checkBraking()
        self.__checkLaneChangeMerge()
        self.__checkObstacle()

        return self.ml

__all__ = ['Frame', 'StaticPackAnalyzer']
