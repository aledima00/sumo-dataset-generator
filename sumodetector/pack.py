from .labels import MultiLabel as _MLB, LabelsEnum as _LE
from dataclasses import dataclass as _dc, field as _field
from .vehicle import Vehicle as _Vehicle
import numpy as _np

@_dc
class Frame:
    vehicles: dict[str, _Vehicle] = _field(default_factory=dict)
    obstacles: dict[str, _Vehicle] = _field(default_factory=dict)
    
    def getVehsByLane(self, lane_id:str) -> list[_Vehicle]:
        vehs = self.vehicles.values()
        return [v for v in vehs if v.lane_id == lane_id]

_DEF_BRAKING_THRESHOLD = -2.0 # m/s^2
_DEF_SLOWDOWN_TRAFFIC_THRESHOLD = 0.1 # ratio of speed reduction to max speed to trigger traffic jam label
_DEF_TRAFFIC_THRESHOLD_CONV_SPEED = 0.1 # how much quickly the threshold speed (init from max speed) converges to observed avg speed

@_dc
class LaneChange:
    id1:str
    id2:str

class StaticPackAnalyzer:
    ml: _MLB
    frames_pack:list[Frame]
    braking_threshold:float
    max_speed_per_lane:dict[str,float]
    traffic_threshold_conv_speed:float
    slowdown_traffic_threshold:float

    def __init__(self, frames_pack:list[Frame],initML:_MLB=None,*, braking_threshold = _DEF_BRAKING_THRESHOLD, max_speed_per_lane:dict[str,float]=None, traffic_threshold_conv_speed:float=_DEF_TRAFFIC_THRESHOLD_CONV_SPEED, slowdown_traffic_threshold:float=_DEF_SLOWDOWN_TRAFFIC_THRESHOLD):
        self.frames_pack = frames_pack
        self.ml = _MLB() if initML is None else initML
        self.braking_threshold = braking_threshold
        self.max_speed_per_lane = max_speed_per_lane
        self.traffic_threshold_conv_speed = traffic_threshold_conv_speed
        self.slowdown_traffic_threshold = slowdown_traffic_threshold

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

    def __checkTrafficJam(self):
        if self.max_speed_per_lane is None:
            return
        baseline_speeds = self.max_speed_per_lane.copy()

        for laneId in self.max_speed_per_lane.keys():
            
            for frame in self.frames_pack:
                vehicles = frame.getVehsByLane(laneId)
                if not vehicles:
                    continue
                avg_speed = _np.mean([v.speed for v in vehicles])

                ratio = avg_speed / baseline_speeds[laneId]
                if ratio < self.slowdown_traffic_threshold:
                    self.ml.setLabel(_LE.TRAFFIC_JAM)
                    return
                else:
                    # update baseline speed towards observed avg speed
                    f = self.traffic_threshold_conv_speed
                    baseline_speeds[laneId] = (1 - f) * baseline_speeds[laneId] + f * avg_speed


    def analyze(self)->_MLB:
        self.__checkBraking()
        self.__checkLaneChangeMerge()
        self.__checkObstacle()
        self.__checkTrafficJam()

        return self.ml

__all__ = ['Edge','Frame', 'Pack', 'StaticPackAnalyzer']
