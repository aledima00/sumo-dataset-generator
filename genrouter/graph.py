import sumolib as _sumolib
from sumolib.net import Net as _Net
from sumolib.net.edge import Edge as _Edge
from sumolib.net.node import Node as _Node
from sumolib.net.connection import Connection as _Conn
from pathlib import Path as _Path
from dataclasses import dataclass as _dc, field as _field
import random as _random

def e2eid(edge:_Edge)->str:
    return edge.getID()
def n2nid(node:_Node)->str:
    return node.getID()


@_dc(frozen=True)
class ConnectionRepresentation:
    from_edge_id:str
    to_edge_id:str
    via_node_id:str

    def isFromEdge(self,edge_id:str)->bool:
        return self.from_edge_id == edge_id
    def isToEdge(self,edge_id:str)->bool:
        return self.to_edge_id == edge_id

@_dc
class JunctionRepresentation:
    node_id:str
    connections:set[ConnectionRepresentation] = _field(default_factory=set)
    def addConnection(self,from_edge_id:str,to_edge_id:str):
        self.connections.add( ConnectionRepresentation(from_edge_id=from_edge_id, to_edge_id=to_edge_id,via_node_id=self.node_id) )

    def getByFromEdge(self,edge_id:str)->set[ConnectionRepresentation]:
        return set( filter( lambda c: c.isFromEdge(edge_id), self.connections ))
    def getByToEdge(self,edge_id:str)->set[ConnectionRepresentation]:
        return set( filter( lambda c: c.isToEdge(edge_id), self.connections ))

@_dc
class RouteRepresentation:
    id:str
    edges:list[str]

    def __init__(self,*,id:str,start_edge_id:str):
        self.id = id
        self.edges = [start_edge_id]

    def xml(self)->str:
        edge_str = ' '.join(self.edges)
        return f'<route id="{self.id}" edges="{edge_str}"/>'

class WalkRepresentation(RouteRepresentation):
    def __init__(self,*,start_edge_id:str):
        super().__init__(id=None, start_edge_id=start_edge_id)
    def xml(self,*,fromTo=False)->str:
        return f'<walk from="{self.edges[0]}" to="{self.edges[-1]}"/>' if fromTo else f'<walk edges="{" ".join(self.edges)}"/>'


class GraphRepresentation:
    __edges:set[str]
    __nodes:set[str]
    __junctions:dict[str,JunctionRepresentation]

    def __addJunction(self, via_node_id:str, from_edge_id:str, to_edge_id:str):
        if via_node_id not in self.__junctions:
            self.__junctions[via_node_id] = JunctionRepresentation(node_id=via_node_id)
        self.__junctions[via_node_id].addConnection(from_edge_id=from_edge_id, to_edge_id=to_edge_id)

    def __getToJunction(self,edge_id:str)->JunctionRepresentation|None:
        for j in self.__junctions.values():
            conns = j.getByFromEdge(edge_id)
            if len(conns)>0:
                return j
        return None

    def __init__(self,netfile:_Path):
        net: _Net = _sumolib.net.readNet(str(netfile))
        edges_raw: list[_Edge] = net.getEdges()
        nodes_raw: list[_Node] = net.getNodes()

        self.__edges = set(map(e2eid, edges_raw))
        self.__nodes = set(map(n2nid, nodes_raw))
        self.__junctions = dict()
        for e in edges_raw:
            
            # e as start
            outgoing_connections: list[_Conn] = [c for sublist in e.getOutgoing().values() for c in sublist]
            incoming_connections: list[_Conn] = [c for sublist in e.getIncoming().values() for c in sublist]

            for conn in outgoing_connections:
                from_edge_id = e2eid(e)
                to_edge_id = e2eid(conn.getTo())
                via_node_id = n2nid(e.getToNode())
                self.__addJunction(via_node_id, from_edge_id, to_edge_id)

            for conn in incoming_connections:
                from_edge_id = e2eid(conn.getFrom())
                to_edge_id = e2eid(e)
                via_node_id = n2nid(e.getFromNode())
                self.__addJunction(via_node_id, from_edge_id, to_edge_id)

    def plot(self):
        print("Edges:")
        for e in self.__edges:
            print(f" - {e}")
        print("Nodes:")
        for n in self.__nodes:
            print(f" - {n}")
        print("Junctions:")
        for jn, j in self.__junctions.items():
            print(f" - Junction {jn}:")
            for c in j.connections:
                print(f"      From edge {c.from_edge_id} to edge {c.to_edge_id} via node {c.via_node_id}")

    def __rt_rand_step(self, rt:RouteRepresentation|WalkRepresentation)->RouteRepresentation|WalkRepresentation:
        last_edge_id = rt.edges[-1]
        to_junction = self.__getToJunction(last_edge_id)
        if to_junction is None:
            return rt # TRUNCATE IF NO JUNCTION
        possible_connections = to_junction.getByFromEdge(last_edge_id)
        next_connection = _random.choice( list(possible_connections) )
        rt.edges.append( next_connection.to_edge_id )

    def randomRoute(self, route_id:str,*,min_steps:int=2, max_steps:int=10, source_edge_ids:set[str]=None)->RouteRepresentation:
        if source_edge_ids is None or len(source_edge_ids)==0:
            source_edge_id = _random.choice( list(self.__edges) )
        else:
            source_edge_id = _random.choice( list(source_edge_ids) )
        rt = RouteRepresentation(id=route_id, start_edge_id=source_edge_id)
        n_steps = _random.randint(min_steps, max_steps)
        for _ in range(n_steps):
            self.__rt_rand_step(rt)
        return rt
    
    def randomWalk(self,*,min_steps:int=2, max_steps:int=10, source_edge_ids:set[str]=None)->WalkRepresentation:
        if source_edge_ids is None or len(source_edge_ids)==0:
            source_edge_id = _random.choice( list(self.__edges) )
        else:
            source_edge_id = _random.choice( list(source_edge_ids) )
        wk = WalkRepresentation(start_edge_id=source_edge_id)
        n_steps = _random.randint(min_steps, max_steps)
        for _ in range(n_steps):
            self.__rt_rand_step(wk)
        return wk


__all__ = ["GraphRepresentation", "RouteRepresentation", "JunctionRepresentation", "ConnectionRepresentation"]