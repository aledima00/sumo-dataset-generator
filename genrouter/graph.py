import random as _RND


class LocDirNode:
    __id:str
    __location:str
    def __init__(self,id:str,location:str):
        self.__id = id
        self.__location = location
    def id(self)->str:
        return self.__id
    def location(self)->str:
        return self.__location
    def __str__(self):
        return f"{self.__id}(@[{self.__location}])"
    def __repr__(self):
        return str(self)
    def __eq__(self, other:'LocDirNode')->bool:
        return self.__id == other.__id
    def __hash__(self):
        return hash(self.__id) # assuming unique ids  
        
class Edge:
    __from:LocDirNode
    __to:LocDirNode
    def __init__(self,from_node:LocDirNode,to_node:LocDirNode):
        self.__from = from_node
        self.__to = to_node
    def from_node(self)->LocDirNode:
        return self.__from
    def to_node(self)->LocDirNode:
        return self.__to
    def jname(self)->str:
        return f"{self.__from.location()}_to_{self.__to.location()}"
    def __str__(self):
        return self.jname()
    def __repr__(self):
        return self.jname()
    def __eq__(self, other:'Edge')->bool:
        return self.__from == other.__from and self.__to == other.__to
    def __hash__(self):
        return hash((self.__from,self.__to))

class Graph:

    class Route:
        path: list[Edge]
        id: str
        src_node: LocDirNode
        def __init__(self,*,id:str,src_node:LocDirNode,graph:'Graph'):
            self.src_node = src_node
            self.id = id
            self.path = []
            self.graph = graph
        def length(self):
            return len(self.path)
        def randAddStep(self):
            current_node = self.path[-1].to_node() if self.length()>0 else self.src_node
            edges = self.graph.edgesFrom(current_node)
            if len(edges)==0:
                return # TRUNCATE IF NO NEIGHBORS
            next_edge = _RND.choice(list(edges))
            self.path.append(next_edge)
        def randExtend(self, steps:int):
            for _ in range(steps):
                self.randAddStep()
        def xml(self):
            totlen = self.length()
            l = " ".join([e.jname() for e in self.path])
            return f'<route id="{self.id}" edges="{l}"/>'

    __nodes:set[LocDirNode]
    __edges:set[Edge]
    def __init__(self,*,nodes:set[LocDirNode]=None,edges:set[Edge]=None):
        self.__nodes = nodes if nodes is not None else set()
        self.__edges = edges if edges is not None else set()
    def addRawNode(self,id:str,location:str):
        node = LocDirNode(id,location)
        if node not in self.__nodes:
            self.__nodes.add(node)
    def addRawEdge(self,from_id:str,to_id:str):
        from_node = next((n for n in self.__nodes if n.id()==from_id),None)
        to_node = next((n for n in self.__nodes if n.id()==to_id),None)
        if from_node is None or to_node is None:
            raise ValueError(f"Nodes with ids {from_id} and/or {to_id} not found in graph")
        edge = Edge(from_node,to_node)
        if edge not in self.__edges:
            self.__edges.add(edge)
    def addRawNodes(self,nodesLocDict:dict[str,set[str]]):
        """
        structure: {location1: {id1,id2,...}, location2: {id3,id4,...}, ...}
        """
        for loc,ids in nodesLocDict.items():
            for id in ids:
                self.addRawNode(id,loc)
    def addRawEdges(self,edgesFromDict:dict[str,set[str]]):
        """
        structure: {from_id1: {to_id1,to_id2,...}, from_id2: {to_id3,to_id4,...}, ...}
        """
        for from_id,to_ids in edgesFromDict.items():
            for to_id in to_ids:
                self.addRawEdge(from_id,to_id)

    def randomNode(self):
        return _RND.choice(list(self.__nodes))
    def nodes(self):
        return self.__nodes
    def edges(self):
        return self.__edges
    
    def edgesFrom(self,node:LocDirNode):
        return {e for e in self.__edges if e.from_node() == node}
    
    def randomRoute(self,id:str,*,min_steps=0,max_steps=None,source_node_ids:list=None):
        steps = _RND.randint(min_steps, max_steps if max_steps is not None else min_steps)
        n = None
        if source_node_ids is not None:
            n_id = _RND.choice(list(source_node_ids))
            n = next((n for n in self.__nodes if n.id()==n_id),None)
            if n is None:
                raise ValueError(f"Source node with id {n_id} not found in graph")
        else:
            n = self.randomNode()
        r = Graph.Route(id=id,src_node=n,graph=self)
        r.randExtend(steps)
        return r
    
__all__ = ["LocDirNode","Edge","Graph"]