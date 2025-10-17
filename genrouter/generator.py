#from generated.roundabout import rawcfg
from .graph import Graph as _G
from .vehicles import VType as _VT, Vehicle as _VH, VParams as _VP, IParams as _IP, VClass as _VC
import random as _RND
from pathlib import Path

ObstacleVtype = _VT(
    "OBSTACLE",
    vp=_VP(
        accel=0.1,
        decel=0.1,
        emergency_decel=0.1,
        length_m=3.0,
        max_speed=0.1,
        kmh=False,
        gui_shape="bus"
    ),
    ip=_IP(
        min_gap_m=0.0,
        speed_factor=0.0,
        speed_dev=0.0
    ),
    additional_attributes={
        "color":"1,0,0",
        "width":"1.0"
    }
)

class Generator:
    def __init__(self,*,OUTPUT_FILE:str,TIME_HORIZON_S:int,N_ROUTES:int,MIN_RTLEN:int,MAX_RTLEN:int,VNUM:int,TDEV_PROP:float,ip_probabs:dict,vp_probabs:dict,vcl_params:dict,graph:_G,probabilistic_mod_multipliers:dict={},source_node_ids:list[str]=None,obstacle_num:int=0):
        self.OUTPUT_FILE = OUTPUT_FILE
        self.TIME_HORIZON_S = TIME_HORIZON_S
        self.N_ROUTES = N_ROUTES
        self.MIN_RTLEN = MIN_RTLEN
        self.MAX_RTLEN = MAX_RTLEN
        self.VNUM = VNUM
        self.TDEV = TDEV_PROP * TIME_HORIZON_S
        self.ip_probabs = ip_probabs
        self.vp_probabs = vp_probabs
        self.vcl_params = vcl_params
        self.vtypes = Generator.__gen_vtypes(ip_probabs,vp_probabs,vcl_params)
        self.graph = graph
        self.probabilistic_mod_multipliers = probabilistic_mod_multipliers
        self.source_node_ids = source_node_ids
        self.obstacle_num = obstacle_num
    
    @staticmethod
    def __gen_vtypes(ip_probabs,vp_probabs,vcl_params):
        vtypes = []
        for ipn,(ipp,ip) in ip_probabs.items():
            for vpn,(vpp,vp) in vp_probabs.items():
                for vcln,(vclp,vcl) in vcl_params.items():
                    vtypes.append( (_VT(f"{vpn}_{ipn}_{vcln}", vp=vp, ip=ip, v_class=vcl), ipp*vpp*vclp))
        return vtypes
    
    @staticmethod
    def __draw_vtype(vtypes)->_VT:
        r = _RND.random()
        acc = 0.0
        for vt,pp in vtypes:
            acc += pp
            if r <= acc:
                return vt
    
    @staticmethod
    def __comment(s:str)->str:
        return f"<!-- {s} -->\n"

    
        
    def apply_random_modificators(self,vt:_VT)->_VT:
        nvt = _VT(vt.id, vp=vt.vp, ip=vt.ip, v_class=vt.v_class)
        for modname,moddata in self.probabilistic_mod_multipliers.items():
            if _RND.random() <= moddata["p"]:
                for attr,mult in moddata["modifications"].items():
                    if hasattr(nvt.vp,attr):
                        setattr(nvt.vp,attr,getattr(nvt.vp,attr)*mult)
                    elif hasattr(nvt.ip,attr):
                        setattr(nvt.ip,attr,getattr(nvt.ip,attr)*mult)
                nvt.id += f"_{modname}"
        return nvt
    
    def generate(self):

        routes = [self.graph.randomRoute(f"RT{i}",min_steps=self.MIN_RTLEN,max_steps=self.MAX_RTLEN,source_node_ids=self.source_node_ids) for i in range(self.N_ROUTES)]
        dts = [max(_RND.gauss(mu=self.TIME_HORIZON_S*i/self.VNUM,sigma=self.TDEV),0.0) for i in range(self.VNUM+self.obstacle_num)]
        used_vtypes = set()
        vehicles:list[_VH] = []
        for i in range(self.VNUM):
            vt = Generator.__draw_vtype(self.vtypes)
            vt = self.apply_random_modificators(vt)
            used_vtypes.add(vt)
            rt = _RND.choice(routes)
            vehicles.append(_VH(f"VEH{i}", vt.id, rt.id, dts[i]))

        for on in range(self.obstacle_num):
            rt = _RND.choice(routes)
            vehicles.append(_VH(f"OBS_{on}", ObstacleVtype.id, rt.id, dts[self.VNUM+on]))

        vehicles.sort(key=lambda v: v.depart_time)

        with open (self.OUTPUT_FILE,'w') as f:
            def wc(s,*,tabs=0):
                f.write(f"{'\t'*tabs}{Generator.__comment(s)}")
            wc(f"Generated vehicle file: {self.N_ROUTES} routes, {self.VNUM} vehicles")
            wc(f">> {self.N_ROUTES} routes, each {self.MIN_RTLEN} to {self.MAX_RTLEN} edges long")
            wc(f">> {self.VNUM} vehicles, depart times ~ N({self.TIME_HORIZON_S/2}s, {self.TDEV}s)")
            wc(f">> Vehicle types from {len(self.vtypes)} combinations, {len(used_vtypes)} used")
            f.write('<routes>\n')

            wc("Routes",tabs=1)
            for r in routes:
                f.write(f'\t{r.xml()}\n')
            f.write('\n')

            wc("Vehicle Types",tabs=1)
            for vt in used_vtypes:
                f.write(f"\t{vt.xml()}\n")
            f.write('\n')

            wc("Obstacle vType",tabs=1)
            f.write(f"\t{ObstacleVtype.xml()}\n\n")
            
            wc("Vehicles",tabs=1)
            for v in vehicles:
                f.write(f"\t{v.xml()}\n")
            f.write('\n')

            f.write('</routes>\n')
            OP = Path(self.OUTPUT_FILE)
            output_shortened = self.OUTPUT_FILE if len(OP.parts)<=3 else Path(OP.parts[0], OP.parts[1], OP.parts[2], "...", OP.parts[-3], OP.parts[-2], OP.parts[-1])
            return {
                "TOTAL SIMULATION TIME (S)": self.TIME_HORIZON_S,
                "NUM. OF ROUTES": self.N_ROUTES,
                "NUM. OF VEHICLES": self.VNUM,
                "NUM. OF VTYPES USED": len(used_vtypes),
                "OBSTACLES": self.obstacle_num,
                "OUTPUT FILE": output_shortened
            }

        print(f"Generated {self.OUTPUT_FILE} with {len(routes)} routes and {len(vehicles)} vehicles, using {len(used_vtypes)} vtypes out of {len(self.vtypes)} possible combinations")