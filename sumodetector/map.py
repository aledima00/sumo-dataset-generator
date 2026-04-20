import sumolib as _sumolib
from dataclasses import dataclass as _dc

from sumolib.net import Net as _Net
from sumolib.net.node import Node as _Node
from sumolib.net.edge import Edge as _Edge
from sumolib.net.lane import Lane as _Lane
from sumolib.net.connection import Connection as _Conn
from enum import Enum as _Enum
import numpy as _np
from numpy import linalg as _la
import pandas as _pd

import traci as _traci
from .vectorMap import sumoNet2df as _sumoNet2df


@_dc
class LaneMergeJunction:
    incoming_edge:_Edge
    junction_node:_Node
    lanes_id_map:dict[str,str]|None =None
    def addLaneMapping(self,from_lane_id:str,to_lane_id:str):
        if self.lanes_id_map is None:
            self.lanes_id_map = dict()
        self.lanes_id_map[from_lane_id] = to_lane_id
    def matchByIncomingEdgeID(self,incoming_edge_id:str)->bool:
        if self.incoming_edge is None or incoming_edge_id is None:
            return False
        return self.incoming_edge.getID() == incoming_edge_id

class MapParser:
    net:_Net
    def __init__(self,netfile_path:str):
        self.net = _sumolib.net.readNet(netfile_path, withInternal=True)
    
    @staticmethod
    def __getLanesAngle(self,from_lane:_Lane,to_lane:_Lane)->float:
        from_shape = from_lane.getShape()
        to_shape = to_lane.getShape()
        v1 = _np.array([from_shape[-1][0]-from_shape[-2][0], from_shape[-1][1]-from_shape[-2][1]])
        v2 = _np.array([to_shape[1][0]-to_shape[0][0], to_shape[1][1]-to_shape[0][1]])
        dotprod = _np.dot(v1, v2)
        norms = _la.norm(v1) * _la.norm(v2)
        cosangle = dotprod / norms
        angle_deg = _np.arccos(cosangle) * (180.0 / _np.pi)
        return angle_deg
    
    def isLaneSpecial(self,lane_id:str)->bool:
        lane: _Lane = self.net.getLane(lane_id)
        if lane is None:
            raise ValueError(f"lane with id {lane_id} not found in the network")
        edge: _Edge = lane.getEdge()
        return edge.isSpecial()

    def getContToLaneId(self,from_lane_id:str):
        """
        Given the arriving lane, returns the outgoing lane with the relative smallest angle, which is assumed to be the continuation of the "main" road.
        """
        from_lane = self.net.getLane(from_lane_id)
        if from_lane is None:
            return ValueError(f"lane with id {from_lane_id} not found in the network")

        incoming_conns: list[_Conn] = from_lane.getOutgoing()
        if len(incoming_conns) == 0:
            return None

        min_angle = 180.0
        cont_lane: _Lane|None = None
        for conn in incoming_conns:
            to_lane: _Lane = conn.getToLane()
            angle = self.__getLanesAngle(self,from_lane,to_lane)
            if angle < min_angle:
                min_angle = angle
                cont_lane = to_lane
        return cont_lane.getID() if cont_lane is not None else None
    

    def asVectorDf(self)->_pd.DataFrame:
        return _sumoNet2df(self.net)
        


    # def getNodeByEdges(self,incoming_edge_id:str,outgoing_edge_id:str)->_Node|None:
    #     ie: _Edge = self.net.getEdge(incoming_edge_id)
    #     oe: _Edge = self.net.getEdge(outgoing_edge_id)
    #     if ie is None or oe is None:
    #         return None
    #     nie: _Node = ie.getToNode()
    #     noe: _Node = oe.getFromNode()
    #     if nie.getID() != noe.getID():
    #         return None
    #     return nie
    
    # def getNodeByInternalEdgeId(self,internal_edge_id:str)->_Node|None:
    #     intedge: _Edge = self.net.getEdge(internal_edge_id)
    #     if intedge is None:
    #         return None
    #     n: _Node = intedge.getFromNode()
    #     return n
    
    # def isTrueJunction(self,from_edge_id:str,to_edge_id:str)->bool:
    #     fe: _Edge = self.net.getEdge(from_edge_id)
    #     te: _Edge = self.net.getEdge(to_edge_id)
    #     if fe is None or te is None:
    #         return False
        

    #     if fe.isSpecial():
    #         jn = self.getNodeByInternalEdgeId(fe.getID())
    #     else:
    #         jn = self.getNodeByEdges(fe.getID(),te.getID())
        
    #     if jn is None:
    #         return False

# def isTrueJunction(self,from_edge:str,to_edge:str)->bool:

#         nodeId = self.getNodeIdByEdges(from_edge,to_edge)
#         if nodeId is None:
#             return False
#         conns = self.connections_by_nodeid[nodeId]
#         incoming_edges = set()
#         outgoing_edges = set()
#         for c in conns:
#             incoming_edges.add(c.getFrom().getID())
#             outgoing_edges.add(c.getTo().getID())
#         return ((len(incoming_edges)+ len(outgoing_edges)) > 2)