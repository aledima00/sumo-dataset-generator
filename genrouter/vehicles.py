from enum import Enum as _EN
from dataclasses import dataclass as _dc

class VClass(_EN):
    PASSENGER = "passenger"
    EMERGENCY = "emergency"
    AUTHORITY = "authority"
    ARMY = "army"
    IGNORING = "ignoring"    

@_dc
class IParams:
    speedFactor:float = 1.0
    speedDev:float = 0.1
    minGap:float = 2.5

    # lane change parameters - keep default for majority of cases
    lcAssertive:float=0.6
    lcSpeedGain:float=0.5
    lcStrategic:float=1.0
    lcLookaheadLeft:float=2.0
    lcLookaheadRight:float=1.0
    lcKeepRight:float=0.7
    lcCooperative:float=0.3
    lcMinGap:float=2.5
    lcMinGapLat:float=0.5
    lcMinGapSpeed:float=5.0
    lcMaxSpeedDeviation:float=5.0
    lcReactionTime:float=0.5

@_dc
class VParams:
    accel:float = 2.6
    decel:float = 4.5
    emergency_decel:float = 9.0
    length_m:float = 5.0
    max_speed:float = 180.0 
    kmh:bool = True
    gui_shape:str = "passenger"

    def __post_init__(self):
        if self.kmh:
            self.max_speed = self.max_speed / 3.6  # convert km/h to m/s
        
    

class VType:
    def __init__(self,id,*,vp:VParams=VParams(), ip:IParams=IParams(), v_class:VClass=VClass.PASSENGER.value, additional_attributes:dict=None):
        self.id = id
        self.vp = vp
        self.ip = ip
        self.v_class = v_class
        self.additional_attributes = additional_attributes if additional_attributes is not None else dict()
    def xml(self):
        x = f'<vType id="{self.id}" accel="{self.vp.accel:.4e}" decel="{self.vp.decel:.4e}" emergencyDecel="{self.vp.emergency_decel:.4e}" length="{self.vp.length_m:.4e}" maxSpeed="{self.vp.max_speed:.4e}" vClass="{self.v_class}" guiShape="{self.vp.gui_shape}"'
        for k,v in self.ip.__dict__.items():
            x += f' {k}="{v:.4e}"'
        for k,v in self.additional_attributes.items():
            x += f' {k}="{v}"'
        
        x += '/>'
        return x
    def __str__(self):
        return str(self.id)
    def __repr__(self):
        return str(self)
    def __hash__(self):
        return hash(self.id)
    def __eq__(self, other):
        return self.id == other.id
    
class Vehicle:
    def __init__(self,id:str, vtype_id:str, route_id:str, depart_time:float):
        self.id = id
        self.vtype_id = vtype_id
        self.route_id = route_id
        self.depart_time = depart_time
    def xml(self):
        return f'<vehicle id="{self.id}" type="{self.vtype_id}" depart="{self.depart_time}" route="{self.route_id}"></vehicle>'
    
__all__ = ["VClass", "IParams", "VParams", "VType", "Vehicle"]