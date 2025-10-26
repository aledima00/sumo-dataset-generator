from dataclasses import dataclass as _dc, field as _field

@_dc
class IParams:
    """
    Generic parameters for the individual driver behavior.
    - speedFactor: multiplier for the speed of the vehicle
    - speedDev: deviation for the speed of the vehicle
    - minGap: minimum gap to the leading vehicle in meters
    Other parameters are related to lane changing and junction behavior.
    """
    speedFactor:float = 1.0
    speedDev:float = 0.1
    minGap:float = 2.5

    # lane change parameters - keep default for majority of cases
    lcStrategic:float=2.0 # how much to exploit lc to reach destinations
    lcCooperative:float=0.5 # how much to perform lc in a cooperative manner
    lcSpeedGain:float=2.0 # how much to exploit lc for speed gain
    lcKeepRight:float=0.7 # how much [0-inf) to return right by default
    lcContRight:float=0.85 # how much [0-1] to choose rightmost lane when available
    lcOvertakeRight:float=0.01 # probability [0-1] to overtake on the right
    lcOpposite:float=0.2 # how much [0-inf) to exploit opposite lane while overtaking
    #lcStrategicLookahead:float=3000.0
    #lcLookaheadLeft:float=2.0
    #lcSpeedGainRight:float=0.1
    lcSpeedGainLookahead:float=4.0 # time in seconds to anticipate slowdowns 
    lcSpeedGainRemainTime:float=20.0 # after strategic lc, how much time to return on lane if no longer needed
    #lcSpeedGainUrgency:float=50.0
    lcAssertive:float=1.0 # willingness [0-inf) to acccept smaller gaps when changing lane
    lcSigma:float=0.5 # imperfection in lateral positioning

    # junction parameters - keep default for majority of cases
    jmIgnoreKeepClearTime:float=10.0 # time in seconds after which keep-clear-junctions are ignored
    jmIgnoreFoeProb:float=0.2 # probability [0-1] to ignore conflicting traffic below jmIgnoreFoeSpeed
    jmIgnoreFoeSpeed:float=10/3.6 # speed (m/s) below which conflicting traffic is ignored
    jmIgnoreJunctionFoeProb:float=0.05 # probability [0-1] to ignore conflicting traffic at junctions
    jmStoplineGap:float=0.3 # gap to stopline in meters
    jmStoplineCrossingGap:float=1.0 # gap to stopline when crossing in meters
    jmStopSignWait:float=3.0 # time in seconds to wait at stop signs
    jmAllwayStopWait:float=3.0 # time in seconds to wait at all-way stops
    impatience:float=0.4 # how much [0-1] to get impatient and impede priority vehicles in traffic jams



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


@_dc
class VType:
    id:str
    vp:VParams = _field(default_factory=VParams)
    ip:IParams = _field(default_factory=IParams)
    vcl:str = "passenger"
    additional_attributes:dict = _field(default_factory=dict)
    def xml(self):
        x = f'<vType id="{self.id}" accel="{self.vp.accel:.4e}" decel="{self.vp.decel:.4e}" emergencyDecel="{self.vp.emergency_decel:.4e}" length="{self.vp.length_m:.4e}" maxSpeed="{self.vp.max_speed:.4e}" vClass="{self.vcl}" guiShape="{self.vp.gui_shape}"'
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
    def __init__(self,id:str, vtype_id:str, route_id:str, depart_time:float,*,additional_attributes:dict=None):
        self.id = id
        self.vtype_id = vtype_id
        self.route_id = route_id
        self.depart_time = depart_time
        self.additional_attributes = additional_attributes if additional_attributes is not None else {}
    def xml(self):
        x = f'<vehicle id="{self.id}" type="{self.vtype_id}" depart="{self.depart_time}" route="{self.route_id}"'
        for k,v in self.additional_attributes.items():
            x += f' {k}="{v}"'
        x += '/>'
        return x

__all__ = ["IParams", "VParams", "VType", "Vehicle"]