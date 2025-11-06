import sumolib as _sumolib
from dataclasses import dataclass as _dc

from sumolib.net import Net as _Net
from sumolib.net.node import Node as _Node
from sumolib.net.edge import Edge as _Edge
from sumolib.net.lane import Lane as _Lane
from sumolib.net.connection import Connection as _Conn
from enum import Enum as _Enum

import traci as _traci

class PedestrianAreaType(_Enum):
    SIDEWALK = "sidewalk"
    WALKINGAREA = "walkingarea"
    CROSSING_NORMAL = "crossing"
    CROSSING_TLS = "crossing_tls"


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
    lm_junctions:list[LaneMergeJunction]
    def __init__(self,netfile_path:str):
        self.net = _sumolib.net.readNet(netfile_path, withInternal=True)
        self.__computeLMJunctions()

    @staticmethod
    def __isLaneMergeJunction(node:_Node)->bool:
        incoming_edges: list[_Edge] = node.getIncoming()
        outgoing_edges: list[_Edge] = node.getOutgoing()

        # before merge, there should be only one edge incoming with multiple lanes
        if len(incoming_edges) != 1:
            return False,None
        incoming_lanes_num = incoming_edges[0].getLaneNumber()
        if incoming_lanes_num < 2:
            return False,None
        
        # proper lane merge if all incoming edges have less lanes than incoming edge
        for oe in outgoing_edges:
            if oe.getLaneNumber() >= incoming_lanes_num:
                return False,None

        lmj = LaneMergeJunction(incoming_edge=incoming_edges[0],junction_node=node) 
        # check that there is a 1:1 mapping from incoming lanes to outgoing lanes
        ilanes:list[_Lane] = incoming_edges[0].getLanes()
        for il in ilanes:
            outgoing_connections:list[_Conn] = il.getOutgoing()
            if len(outgoing_connections) != 1:
                return False,None
            ol: _Lane = outgoing_connections[0].getToLane()
            lmj.addLaneMapping(il.getID(),ol.getID())

        return True, lmj
    
    def __computeLMJunctions(self):
        self.lm_junctions: list[LaneMergeJunction] = []
        nodes: list[_Node] = self.net.getNodes()
        for n in nodes:
            is_lmj, lmj = self.__isLaneMergeJunction(n)
            if is_lmj:
                self.lm_junctions.append(lmj)

    def checkIfLcLm(self,from_lane_id:str,to_lane_id:str)->bool:

        from_lane = self.net.getLane(from_lane_id)
        to_lane = self.net.getLane(to_lane_id)
        
        lane_merge_junction = next((lmj for lmj in self.lm_junctions if lmj.matchByIncomingEdgeID(from_lane.getEdge().getID())),None)
        if lane_merge_junction is None or lane_merge_junction.lanes_id_map is None:
            return False
        
        out_l_from = lane_merge_junction.lanes_id_map.get(from_lane.getID(),None)
        out_l_to = lane_merge_junction.lanes_id_map.get(to_lane.getID(),None)
        out_e_from = _traci.lane.getEdgeID(out_l_from) if out_l_from is not None else None
        out_e_to = _traci.lane.getEdgeID(out_l_to) if out_l_to is not None else None

        # lc is lm if the lc correspond to different outgoing edges after the lane merge junction
        return out_e_from != out_e_to
    
    def isPedestrianArea(self,lane_id:str)->tuple[bool,PedestrianAreaType|None]:
        """
        Check if the given lane belongs to a pedestrian area, that is either
        - a "sidewalk" restricted lane
        - a lane from a "walkingarea" edge
        - a lane from a "crossing" edge
        """
        if lane_id is None:
            raise ValueError("lane_id cannot be None")
        lane: _Lane = self.net.getLane(lane_id)
        if lane is None:
            raise ValueError(f"lane with id {lane_id} not found in the network")
        edge: _Edge = lane.getEdge()
        
        if edge.getFunction() == "crossing":
            trueConn: _Conn = lane.getConnection()
            if trueConn is None:
                raise ValueError(f"lane with id {lane_id} has no connection, cannot determine if crossing with tls")
            tlsind = trueConn.getTLLinkIndex()
            if tlsind is not None and tlsind >= 0:
                return True, PedestrianAreaType.CROSSING_TLS
            else:
                return True, PedestrianAreaType.CROSSING_NORMAL
        elif edge.getFunction() == "walkingarea":
            return True, PedestrianAreaType.WALKINGAREA
        else:
            allowed = lane.getPermissions()
            if allowed is not None and len(allowed) == 1 and "pedestrian" in allowed:
                return True, PedestrianAreaType.SIDEWALK
            else:
                return False, None


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