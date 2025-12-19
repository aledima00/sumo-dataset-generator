import sumolib as _sumolib
from sumolib.net import Net as _Net
from sumolib.net.edge import Edge as _Edge
from sumolib.net.lane import Lane as _Lane

from enum import IntEnum as _IE
from typing import TypeAlias as _TA
import pandas as _pd

class TrafficCatEnum(_IE):
    UNKNOWN = 0
    EMERGENCY = 1
    AUTHORITY = 2
    ARMY = 3
    PEDESTRIAN = 4
    PASSENGER = 5
    BICYCLE = 6

    @classmethod
    def fromStr(cls, scat:str):
        match scat.lower():
            case "emergency":
                return cls.EMERGENCY
            case "authority":
                return cls.AUTHORITY
            case "army":
                return cls.ARMY
            case "pedestrian":
                return cls.PEDESTRIAN
            case "passenger":
                return cls.PASSENGER
            case "bicycle":
                return cls.BICYCLE
            case _:
                return cls.UNKNOWN
            
        
    @classmethod
    def encodeCategoriesStrAsUint8(cls, categories:set[str])->int:
        enc = 0
        for catstr in categories:
            enc |= (1 << cls.fromStr(catstr).value)
        return enc



Point: _TA = tuple[float,float]
Segment: _TA = tuple[Point,Point]


class EdgeFuncType(_IE):
    """Enum for different types of lanes."""
    EDGE_UNKNOWN= 0
    EDGE_NORMAL= 1
    EDGE_JUNCTION_INTERNAL= 2
    EDGE_CROSSING= 3
    EDGE_WALKINGAREA= 4

    @classmethod
    def fromStr(cls,eftstr:str):
        match eftstr.lower():
            case "normal" | "connector":
                return cls.EDGE_NORMAL
            case "internal":
                return cls.EDGE_JUNCTION_INTERNAL
            case "crossing":
                return cls.EDGE_CROSSING
            case "walkingarea":
                return cls.EDGE_WALKINGAREA
            case _:
                return cls.EDGE_UNKNOWN
class Lane:
    # data
    allowedTrafficEnc: int
    speed_limit: float
    width: float
    polyline_center: list[Segment]

    # priority: int|None
    def __init__(self, allowedTrafficEnc:int, speed_limit:float, width:float):
        self.allowedTrafficEnc = allowedTrafficEnc
        self.speed_limit = speed_limit
        self.width = width
        self.polyline_center = []

    def addSegmentToCenterline(self, s:Segment):
        slast = None if len(self.polyline_center) == 0 else self.polyline_center[-1]
        if slast is not None and slast[1] != s[0]:
            raise ValueError("Segment start point does not match last segment end point.")
        self.polyline_center.append(s)

    def asPandas(self)->_pd.DataFrame|None:

        if len(self.polyline_center)<=1:
            return None

        df = _pd.DataFrame([{
            "start_x": seg[0][0],
            "start_y": seg[0][1],
            "end_x": seg[1][0],
            "end_y": seg[1][1],
        } for seg in self.polyline_center]).astype({
            "start_x": "float32",
            "start_y": "float32",
            "end_x": "float32",
            "end_y": "float32",
        })

        
        df["allowed_traffic_enc"] = _pd.Series(self.allowedTrafficEnc, index=df.index, dtype="uint8")
        df["speed_limit"] = _pd.Series(self.speed_limit, index=df.index, dtype="float32")
        df["width"] = _pd.Series(self.width, index=df.index, dtype="float32")

        return df
    
def sumoNet2df(sumo_net:_Net)->_pd.DataFrame:
    edges: list[_Edge] = sumo_net.getEdges(withInternal=False)
    df = None
    for edge in edges:
        edge_df = sumoEdge2df(edge)
        if edge_df is not None:
            if df is None:
                df = edge_df
            elif edge_df is not None:
                df = _pd.concat([df, edge_df], ignore_index=True)
    if df is None:
        df = _pd.DataFrame()
    return df

def sumoEdge2df(sumo_edge:_Edge,*,function:bool=False)->_pd.DataFrame|None:
    eid = sumo_edge.getID()
    if function:
        edge_function = EdgeFuncType.fromStr(sumo_edge.getFunction())

    # now loop over lanes to get lane-specific info
    sumo_lanes: list[_Lane] = sumo_edge.getLanes()

    df = None

    for sumo_lane in sumo_lanes:
        lane_df = sumoLane2df(sumo_lane)
        if df is None:
            df = lane_df
        elif lane_df is not None:
            df = _pd.concat([df, lane_df], ignore_index=True)
    

    if df is not None:
        # add edge-wise info to df
        if function:
            df["edge_function"] = _pd.Series(edge_function, index=df.index, dtype="uint8")
        df["edge_id"] = _pd.Series(eid, index=df.index, dtype="string")
    
    return df

def sumoLane2df(sumo_lane:_Lane)->_pd.DataFrame|None:
    # determine allowed traffic
    allowed_traffic_enc = TrafficCatEnum.encodeCategoriesStrAsUint8(sumo_lane.getPermissions())
    
    # speed limit
    speed_limit = sumo_lane.getSpeed()

    # width
    width = sumo_lane.getWidth()
    
    # create Lane object
    laneobj = Lane(allowed_traffic_enc, speed_limit, width)

    # centerline polyline
    centerline_coords = sumo_lane.getShape(includeJunctions=True)
    # build segments as pairs of points
    for i in range(len(centerline_coords)-1):
        pstart = centerline_coords[i]
        pend = centerline_coords[i+1]
        segment = ((pstart[0],pstart[1]),(pend[0],pend[1]))
        laneobj.addSegmentToCenterline(segment)

    return laneobj.asPandas()
    