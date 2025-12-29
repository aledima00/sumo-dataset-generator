from dataclasses import dataclass as _dc, field as _field, asdict as _asdict
from .station import StationType as _ST
from .mappingFunctions import mapping_functions as _mf
_mf.setEps(1e-6)

class IParams:
    """
    Generic parameters for the individual driver behavior.
    - speedFactor: multiplier for the speed of the vehicle
    - speedDev: deviation for the speed of the vehicle
    - minGap: minimum gap to the leading vehicle in meters
    Other parameters are related to lane change and junction behavior.
    """

    def __init__(self,speedFactor:float=1.0,speedDev:float=0.1,minGap:float=2.5, lcAggressiveness:float=0.1, lcGreediness:float=0.5, jcAggressiveness:float=0.1):
        self.generalDict = {
            "speedFactor": speedFactor,
            "speedDev": speedDev,
            "minGap": minGap
        }
        self.lcAggressivenessDict = dict()
        self.lcGreedinessDict = dict()
        self.jcAggressivenessDict = dict()

        self.setLcAggressiveness(lcAggressiveness)
        self.setLcGreediness(lcGreediness)
        self.setJcAggressiveness(jcAggressiveness)

    def setLcAggressiveness(self,lc_aggressiveness):
        assert 0.0 <= lc_aggressiveness <= 1.0, "lc_aggressiveness must be in [0-1]"
        self.__lc_aggressiveness = lc_aggressiveness

        self.lcAggressivenessDict["lcCooperative"] = _mf.neglin_01_scaled(lc_aggressiveness) # how much to perform lc in a cooperative manner
        self.lcAggressivenessDict["lcOvertakeRight"] = _mf.exp_01_10(lc_aggressiveness,strength=5.0) # probability to overtake on the right
        self.lcAggressivenessDict["lcOpposite"] = _mf.inv_01_0inf(lc_aggressiveness,strength=5.0) # how much [0-inf) to exploit opposite lane while overtaking
        self.lcAggressivenessDict["lcSigma"] = _mf.lin_01_scaled(lc_aggressiveness,min_val=0.1,max_val=0.8) # lc imperfection in lateral positioning
        self.lcAggressivenessDict["lcAssertive"] = _mf.inv_01_0inf(lc_aggressiveness,strength=3.0) # willingness [0-inf) to acccept smaller gaps when changing lane

    def setLcGreediness(self,lc_greediness:float=1.0):
        assert 0.0 <= lc_greediness <= 1.0, "lc_greediness must be in [0-1]"
        self.__lc_greediness = lc_greediness

        self.lcGreedinessDict["lcStrategic"] = _mf.inv_01_0inf(lc_greediness,strength=5.0) # how much to exploit lc to reach destinations
        self.lcGreedinessDict["lcSpeedGain"] = _mf.inv_01_0inf(lc_greediness,strength=5.0) # how much to exploit lc for speed gain
        self.lcGreedinessDict["lcKeepRight"] = 1.0 # how much [0-inf) to return right by default
        self.lcGreedinessDict["lcContRight"] = _mf.lin_01_scaled(lc_greediness) # how much [0-1] to choose rightmost lane when available
        self.lcGreedinessDict["lcSpeedGainLookahead"] = _mf.lin_01_scaled(lc_greediness,1.0,4.0) # time in seconds to anticipate slowdowns 
        self.lcGreedinessDict["lcSpeedGainRemainTime"] = _mf.neglin_01_scaled(lc_greediness,5.0,20.0) # after speed gain lc, how much time to return on lane if no longer needed
        self.lcGreedinessDict["lcOvertakeDeltaSpeedFactor"] = _mf.lin_01_scaled(lc_greediness,-1,1) # multiplier for the delta speed needed to overtake

    # junction parameters - keep default for majority of cases
    def setJcAggressiveness(self,jc_aggressiveness:float=0.0):
        assert 0.0 <= jc_aggressiveness <= 1.0, "jc_aggressiveness must be in [0-1]"
        self.__jc_aggressiveness = jc_aggressiveness

        # time based parameters - linear dep. is ok
        self.jcAggressivenessDict["jmIgnoreKeepClearTime"] = _mf.neglin_01_scaled(jc_aggressiveness, 4.0, 12.0) # time after which vehicles enter a junction even if causing a traffic jam
        self.jcAggressivenessDict["jmStopSignWait"] = _mf.neglin_01_scaled(jc_aggressiveness, 1.0, 3.0) # time to wait at stop signs
        self.jcAggressivenessDict["jmAllwayStopWait"] = _mf.neglin_01_scaled(jc_aggressiveness, 1.0, 3.0) # time to wait at all-way stops

        # probability based parameters - use exp. mapping to slow down changes at low aggressiveness
        self.jcAggressivenessDict["jmIgnoreFoeProb"] = _mf.exp_01_01(jc_aggressiveness,strength=10) # probability to ignore conflicting traffic below jmIgnoreFoeSpeed - linear in [0-1]
        self.jcAggressivenessDict["jmIgnoreFoeSpeed"] = _mf.exp_01_01(jc_aggressiveness,10/3.6) # speed (m/s) below which conflicting traffic is ignored
        self.jcAggressivenessDict["jmIgnoreJunctionFoeProb"] = _mf.exp_01_01(jc_aggressiveness,strength=5) # probability to ignore conflicting traffic at junctions 
        self.jcAggressivenessDict["jmAdvance"] = 0 if jc_aggressiveness < 0.5 else 1  # whether to try to advance in junctions when possible
        self.jcAggressivenessDict["impatience"] = _mf.exp_01_01(jc_aggressiveness) # how much to get impatient and impede priority vehicles in traffic jams
        

    @property
    def jc_aggressiveness(self) -> float:
        return self.__jc_aggressiveness
    
    @jc_aggressiveness.setter
    def jc_aggressiveness(self, value: float):
        self.setJcAggressiveness(value)

    @property
    def lc_aggressiveness(self) -> float:
        return self.__lc_aggressiveness
    
    @lc_aggressiveness.setter
    def lc_aggressiveness(self, value: float):
        self.setLcAggressiveness(value)

    @property
    def lc_greediness(self) -> float:
        return self.__lc_greediness
    
    @lc_greediness.setter
    def lc_greediness(self, value: float):
        self.setLcGreediness(value)
    

    def copy(self):
        return IParams(
            speedFactor=self.generalDict["speedFactor"],
            speedDev=self.generalDict["speedDev"],
            minGap=self.generalDict["minGap"],
            lcAggressiveness=self.lc_aggressiveness,
            lcGreediness=self.lc_greediness,
            jcAggressiveness=self.jc_aggressiveness
        )
    
    def setActionStepLength(self,asl:float):
        self.generalDict["actionStepLength"] = asl   

    def asDict(self) -> dict:
        d = dict()
        d.update(self.generalDict)
        d.update(self.lcAggressivenessDict)
        d.update(self.lcGreedinessDict)
        d.update(self.jcAggressivenessDict)
        return d


@_dc
class VParams:
    stType: int = _ST.PASSENGER_CAR.value
    accel:float = 2.6
    decel:float = 4.5
    emergency_decel:float = 9.0
    length_m:float = 5.0
    max_speed:float = 180.0 
    kmh:bool = True
    gui_shape:str = "passenger"
    apparent_decel:float = None  # if set

    def __post_init__(self):
        if self.kmh:
            self.max_speed = self.max_speed / 3.6  # convert km/h to m/s
        if self.apparent_decel is None:
            self.apparent_decel = self.decel

    def copy(self):
        return VParams(**_asdict(self))


@_dc
class VType:
    name:str
    vp:VParams = _field(default_factory=VParams)
    ip:IParams = _field(default_factory=IParams)
    vcl:str = "passenger"
    additional_attributes:dict = _field(default_factory=dict)
    
    @property
    def station_type(self) -> _ST:
        return _ST(self.vp.stType)

    @property
    def id(self) -> str:
        return f"ST{self.station_type.value:03d}_{self.name}"
    def xml(self):
        x = f'<vType id="{self.id}" accel="{self.vp.accel:.4e}" decel="{self.vp.decel:.4e}" emergencyDecel="{self.vp.emergency_decel:.4e}" length="{self.vp.length_m:.4e}" maxSpeed="{self.vp.max_speed:.4e}" vClass="{self.vcl}" guiShape="{self.vp.gui_shape}" apparentDecel="{self.vp.apparent_decel:.4e}"'
        for k,v in self.ip.asDict().items():
            if v is not None:
                x += f' {k}="{v:.4e}"'
        for k,v in self.additional_attributes.items():
            x += f' {k}="{v}"'
        
        x += '/>'
        return x
    def copy(self):
        return VType(name=self.name, vp=self.vp.copy(), ip=self.ip.copy(), vcl=self.vcl, additional_attributes=self.additional_attributes.copy())
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