import random

class Graph:
    def __init__(self,*,nodes_raw:tuple[str,str,str,str],edges_raw:list[tuple[str,str]]):
        self.__nodes_raw = nodes_raw
        self.__edges_raw = edges_raw


        class Node:
            def __init__(self,nodename):
                if nodename not in nodes_raw:
                    raise ValueError(f"Node {nodename} not in nodes_raw")
                self.nodename = nodename
                
            def __str__(self):
                return self.nodename
            def __repr__(self):
                return str(self)
            def neighbors(self):
                return [Node(n2) for (n1,n2) in edges_raw if n1==self.nodename]
            def edgeWith(self, other:'Node')->str:
                return f"{self}_to_{other}"
            def edgeCheck(self, other:'Node')->bool:
                return other in self.neighbors()
            def __eq__(self, other):
                return self.nodename == other.nodename
            def __hash__(self):
                return hash(self.nodename)
        class Route:
            def __init__(self, path:list[Node]=[],*,id:str,no_turnback:bool=True):
                self.path = path
                self.id = id
                self.no_turnback = no_turnback
            def xml(self):
                l = " ".join([self.path[i].edgeWith(self.path[i+1]) for i in range(len(self.path)-1)])
                return f'<route id="{self.id}" edges="{l}"/>'
            def __str__(self):
                return str(self.id)
            def __repr__(self):
                return str(self)
            def length(self):
                return max(0,len(self.path)-1)
            def randAddStep(self,*,truncate_if_no_neighbors:bool=False):
                if len(self.path)==0:
                    self.path.append(Node.random())
                else:
                    current_node = self.path[-1]
                    exclude_nodes = [self.path[-2]] if (self.no_turnback and len(self.path)>1) else []
                    neighbors = [n for n in current_node.neighbors() if n not in exclude_nodes]
                    if len(neighbors)==0:
                        if truncate_if_no_neighbors:
                            return
                        raise ValueError(f"No available neighbors to extend route {self.id} from node {current_node}")
                    next_node = random.choice(neighbors)
                    self.path.append(next_node)
            def randExtend(self, steps:int):
                for _ in range(steps):
                    self.randAddStep(truncate_if_no_neighbors=True)


        self.NCL = Node
        self.RCL = Route
        self.__nodes = [Node(n) for n in nodes_raw]
    def randomNode(self):
        return random.choice(self.__nodes)
    def nodes(self):
        return self.__nodes
    def randomRoute(self,id:str,*,no_turnback:bool=True,min_steps=0,max_steps=None,from_node=None):
        steps = random.randint(min_steps, max_steps if max_steps is not None else min_steps)
        n = from_node if from_node is not None else self.randomNode()
        r = self.RCL([n],id=id,no_turnback=no_turnback)
        r.randExtend(steps)
        return r