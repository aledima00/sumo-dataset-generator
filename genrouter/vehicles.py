from enum import Enum as _EN
class VClass(_EN):
    PASSENGER = "passenger"
    EMERGENCY = "emergency"
    AUTHORITY = "authority"
    ARMY = "army"
    IGNORING = "ignoring"    

class IParams:
    def __init__(self,speed_factor=1.0, speed_dev=0.1, min_gap_m=2.5):
        self.speed_factor = speed_factor
        self.speed_dev = speed_dev
        self.min_gap = min_gap_m
class VParams:
    def __init__(self,accel=2.6, decel=4.5, emergency_decel=9.0, length_m=5.0, max_speed=180.0,*,kmh=True,gui_shape:str="passenger"):
        self.accel = accel
        self.decel = decel
        self.emergency_decel = emergency_decel
        self.length = length_m
        self.max_speed = max_speed if not kmh else max_speed / 3.6  # convert km/h to m/s
        self.gui_shape = gui_shape

class VType:
    def __init__(self,id,*,vp:VParams=VParams(), ip:IParams=IParams(), v_class:VClass=VClass.PASSENGER.value,additional_attributes:dict=None):
        self.id = id
        self.vp = vp
        self.ip = ip
        self.v_class = v_class
        self.additional_attributes = additional_attributes if additional_attributes is not None else dict()
    def xml(self):
        x = f'<vType id="{self.id}" accel="{self.vp.accel}" decel="{self.vp.decel}" emergencyDecel="{self.vp.emergency_decel}" length="{self.vp.length}" maxSpeed="{self.vp.max_speed}" minGap="{self.ip.min_gap}" speedFactor="{self.ip.speed_factor}" speedDev="{self.ip.speed_dev}" vClass="{self.v_class}" guiShape="{self.vp.gui_shape}"'
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