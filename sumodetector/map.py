from pathlib import Path as _Path
from xml.etree import ElementTree as _ET
import sumolib as _sumolib

from sumolib.net import Net as _Net
from sumolib.net.node import Node as _Node
from sumolib.net.edge import Edge as _Edge

class MapParser:
    net:_Net
    def __init__(self,netfile_path:str):
        self.net = _sumolib.net.readNet(netfile_path)


    def getNodeByEdges(self,incoming_edge_id:str,outgoing_edge_id:str)->_Node|None:
        ie: _Edge = self.net.getEdge(incoming_edge_id)
        oe: _Edge = self.net.getEdge(outgoing_edge_id)
        if ie is None or oe is None:
            return None
        nie: _Node = ie.getToNode()
        noe: _Node = oe.getFromNode()
        if nie.getID() != noe.getID():
            return None
        return nie
    
    def getNodeByInternalEdgeId(self,internal_edge_id:str)->_Node|None:
        intedge: _Edge = self.net.getEdge(internal_edge_id)
        if intedge is None:
            return None
        n: _Node = intedge.getFromNode()
        return n
    
    def isTrueJunction(self,from_edge_id:str,to_edge_id:str)->bool:
        fe: _Edge = self.net.getEdge(from_edge_id)
        te: _Edge = self.net.getEdge(to_edge_id)
        if fe is None or te is None:
            return False
        

        if fe.isSpecial():
            jn = self.getNodeByInternalEdgeId(fe.getID())
        else:
            jn = self.getNodeByEdges(fe.getID(),te.getID())
        
        if jn is None:
            return False
        







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