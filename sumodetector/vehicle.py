from dataclasses import dataclass as _dc
import traci as _traci

@_dc
class Vehicle:
    id:str = None
    lane_id:str = None
    speed:float = 0.0
    acceleration:float = 0.0


    @classmethod
    def from_traci(cls, vid:str):
        return cls(
            id=vid,
            lane_id=_traci.vehicle.getLaneID(vid),
            speed=_traci.vehicle.getSpeed(vid),
            acceleration=_traci.vehicle.getAcceleration(vid)
        )
    
__all__ = ['Vehicle']
