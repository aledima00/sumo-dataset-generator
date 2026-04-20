from sumolib.net import Net as _Net
from sumolib.net.edge import Edge as _Edge
from sumolib.net.lane import Lane as _Lane

from enum import IntEnum as _IE
from typing import TypeAlias as _TA
import pandas as _pd


Point: _TA = tuple[float,float]
Segment: _TA = tuple[Point,Point]

class Lane:
    class LaneType(_IE):
        LANE_NORMAL = 0 # DEFAULT
        LANE_SIDEWALK = 1
        LANE_CROSSING = 2
        LANE_BICYCLE = 3
        LANE_BUS = 4
        LANE_WKAREA = 5

        @staticmethod
        def fromPermissionsAndFunction(permissions:set[str],function:str) -> 'Lane.LaneType':

            lp = len(permissions) if permissions is not None else 0
            
            if function == 'crossing':
                return Lane.LaneType.LANE_CROSSING
            elif function == 'walkingarea':
                return Lane.LaneType.LANE_WKAREA
            elif lp==0:
                return Lane.LaneType.LANE_NORMAL
            elif lp == 1:
                if 'pedestrian' in permissions:
                    return Lane.LaneType.LANE_SIDEWALK
                elif 'bicycle' in permissions:
                    return Lane.LaneType.LANE_BICYCLE
                elif 'bus' in permissions:
                    return Lane.LaneType.LANE_BUS
            else:
                return Lane.LaneType.LANE_NORMAL
    
    # data
    laneType: LaneType
    speed_limit: float
    width: float
    polyline_center: list[Segment]
    canGoLeft: bool
    canGoRight: bool

    # priority: int|None
    def __init__(self, speed_limit:float, width:float, laneType:LaneType=None, canGoLeft:bool=False, canGoRight:bool=False):
        self.speed_limit = speed_limit
        self.width = width
        self.laneType = laneType if laneType is not None else Lane.LaneType.LANE_NORMAL
        self.polyline_center = []
        self.canGoLeft = canGoLeft
        self.canGoRight = canGoRight
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

        
        df["lane_type"] = _pd.Series(self.laneType.value, index=df.index, dtype="uint8")
        df["speed_limit"] = _pd.Series(self.speed_limit, index=df.index, dtype="float32")
        df["width"] = _pd.Series(self.width, index=df.index, dtype="float32")
        df["can_go_left"] = _pd.Series(self.canGoLeft, index=df.index, dtype="bool")
        df["can_go_right"] = _pd.Series(self.canGoRight, index=df.index, dtype="bool")

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

def sumoEdge2df(sumo_edge:_Edge)->_pd.DataFrame|None:
    #eid = sumo_edge.getID()
    edgeFunction = sumo_edge.getFunction()

    # now loop over lanes to get lane-specific info
    sumo_lanes: list[_Lane] = sumo_edge.getLanes()
    num_lanes = len(sumo_lanes)

    df = None

    for sumo_lane in sumo_lanes:
        lane_df = sumoLane2df(sumo_lane, edgeFunction=edgeFunction, edge_lane_nums=num_lanes)
        if df is None:
            df = lane_df
        elif lane_df is not None:
            df = _pd.concat([df, lane_df], ignore_index=True)
    
    return df

def sumoLane2df(sumo_lane:_Lane, edgeFunction:str, edge_lane_nums:int)->_pd.DataFrame|None:
    # determine lane type
    lane_type = Lane.LaneType.fromPermissionsAndFunction(
        permissions=sumo_lane.getPermissions(),
        function=edgeFunction
    )
    
    # speed limit
    speed_limit = sumo_lane.getSpeed()

    # width
    width = sumo_lane.getWidth()

    # lane can go left/right
    edge_idx = sumo_lane.getIndex()
    canGoLeft = edge_idx > 0
    canGoRight = edge_idx < (edge_lane_nums - 1)
    
    # create Lane object
    laneobj = Lane(speed_limit, width, laneType=lane_type, canGoLeft=canGoLeft, canGoRight=canGoRight)

    # centerline polyline
    centerline_coords = sumo_lane.getShape(includeJunctions=True)
    # build segments as pairs of points
    for i in range(len(centerline_coords)-1):
        pstart = centerline_coords[i]
        pend = centerline_coords[i+1]
        segment = ((pstart[0],pstart[1]),(pend[0],pend[1]))
        laneobj.addSegmentToCenterline(segment)

    return laneobj.asPandas()
    