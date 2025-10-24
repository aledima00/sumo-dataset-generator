from .graph import GraphRepresentation as _GR
from .vehicles import VType as _VT, Vehicle as _VH, VParams as _VP, IParams as _IP
import random as _RND
from pathlib import Path as _Path
from .genopts import GenOptions as _GenOptions

ObstacleVtype = _VT(
    id="OBSTACLE",
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
        minGap=0.0,
        speedFactor=0.0,
        speedDev=0.0
    ),
    additional_attributes={
        "color":"1,0,0",
        "width":"1.0"
    }
)

class Generator:
    def __init__(self,*,gparams:_GenOptions,OUTPUT_FILE:_Path,TIME_HORIZON_S:int,graph:_GR,source_edge_ids:list[str]=None):
        self.OUTPUT_FILE = OUTPUT_FILE
        self.TIME_HORIZON_S = TIME_HORIZON_S
        self.N_ROUTES = gparams.nroutes
        self.MIN_RTLEN = gparams.minrtlen
        self.MAX_RTLEN = gparams.maxrtlen
        self.VNUM = gparams.vnum
        self.TDEV = gparams.tdevp * TIME_HORIZON_S
        self.obstacle_num = gparams.obstacles
        self.ip_probabs = gparams.IPDict()
        self.vp_probabs = gparams.VPDict()
        self.vcl_probabs = gparams.VCLDict()
        self.probabilistic_mod_multipliers = gparams.PMDict()
        self.vtypes = self.__gen_vtypes()
        self.graph = graph
        self.source_edge_ids = source_edge_ids
        self.num_used_vtypes = 0
    
    def __gen_vtypes(self):
        vtypes = []
        for ipn,(ipp,ip) in self.ip_probabs.items():
            for vpn,(vpp,vp) in self.vp_probabs.items():
                for vcln,(vclp,vcl) in self.vcl_probabs.items():
                    vtypes.append( (_VT(id=f"{vpn}_{ipn}_{vcln}", vp=vp, ip=ip, vcl=vcl), ipp*vpp*vclp))
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
        nvt = _VT(id=vt.id, vp=vt.vp, ip=vt.ip, vcl=vt.vcl)
        for modname,moddata in self.probabilistic_mod_multipliers.items():
            p,mods = moddata
            if _RND.random() <= p:
                for attr,mult in mods.items():
                    if hasattr(nvt.vp,attr):
                        setattr(nvt.vp,attr,getattr(nvt.vp,attr)*mult)
                    elif hasattr(nvt.ip,attr):
                        setattr(nvt.ip,attr,getattr(nvt.ip,attr)*mult)
                nvt.id += f"_{modname}"
        return nvt
    
    def generate(self):

        routes = [self.graph.randomRoute(route_id=f"RT{i}",min_steps=self.MIN_RTLEN,max_steps=self.MAX_RTLEN,source_edge_ids=self.source_edge_ids) for i in range(self.N_ROUTES)]
        dts = [max(_RND.gauss(mu=self.TIME_HORIZON_S*i/self.VNUM,sigma=self.TDEV),0.0) for i in range(self.VNUM+self.obstacle_num)]
        _RND.shuffle(dts)
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
        self.num_used_vtypes = len(used_vtypes)

__all__ = ["Generator"]