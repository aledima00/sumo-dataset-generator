from .graph import GraphRepresentation as _GR
from .vehicles import VType as _VT, Vehicle as _VH, VParams as _VP, IParams as _IP
from .persons import Person as _Person, PType as _PT
import random as _RND
from pathlib import Path as _Path
from .genopts import GenOptions as _GenOptions
from .station import StationType as _ST

additional_attributes={
    "departPos":"random_free",
    "arrivalLane":"first",
    "arrivalSpeed":"0.0",
    "departPosLat":"right",
    "arrivalPosLat":"right",
    "insertionChecks":"none"
}

ObstacleVtype = _VT(
    name="OBSTACLE",
    vp=_VP(
        stType=_ST.UNSPECIFIED.value,
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
    def __init__(self,*,gparams:_GenOptions,OUTPUT_FILE:_Path,TIME_HORIZON_S:int,graph:_GR):
        self.OUTPUT_FILE = OUTPUT_FILE
        self.TIME_HORIZON_S = TIME_HORIZON_S
        self.N_ROUTES = gparams.nroutes
        self.N_WALKS = gparams.nwalks
        self.MIN_RTLEN = gparams.minrtlen
        self.MAX_RTLEN = gparams.maxrtlen
        self.MAX_WALKLEN = gparams.maxwalklen
        self.MIN_WALKLEN = gparams.minwalklen
        self.VNUM = gparams.vnum
        self.PNUM = gparams.pnum
        self.TDEV = gparams.tdevp * TIME_HORIZON_S
        self.obstacle_num = gparams.obstacles
        self.ip_probabs = gparams.IPDict()
        self.vp_probabs = gparams.VPDict()
        self.vcl_probabs = gparams.VCLDict()
        self.prs_params = gparams.PPDict()
        self.probabilistic_mod_multipliers = gparams.PMDict()
        self.source_edge_ids = gparams.source_edges
        self.vtypes = self.__gen_vtypes()
        self.ptypes = self.__gen_ptypes()
        self.graph = graph
        self.num_used_vtypes = 0
    
    def __gen_vtypes(self):
        vtypes = []
        for ipn,(ipp,ip) in self.ip_probabs.items():
            for vpn,(vpp,vp) in self.vp_probabs.items():
                for vcln,(vclp,vcl) in self.vcl_probabs.items():
                    vtypes.append( (_VT(name=f"{vpn}_{ipn}_{vcln}", vp=vp, ip=ip, vcl=vcl,additional_attributes=additional_attributes), ipp*vpp*vclp))
        return vtypes
    
    def __gen_ptypes(self):
        ptypes = []
        for ppn,(ppp,pp) in self.prs_params.items():
            ptypes.append( (_PT(name=ppn, pp=pp), ppp) )
        return ptypes
    
    def __gen_vehicles(self,routes):
        used_vtypes = set()
        vehicles:list[_VH] = []
        dpts = [max(_RND.gauss(mu=self.TIME_HORIZON_S*i/(self.VNUM+self.obstacle_num),sigma=self.TDEV),0.0) for i in range(self.VNUM+self.obstacle_num)]
        for i in range(self.VNUM):
            vt = Generator.__draw_vtype(self.vtypes)
            vt = self.apply_random_modificators(vt)
            used_vtypes.add(vt)
            rt = _RND.choice(routes)
            vehicles.append(_VH(f"VEH_{i}", vt.id, rt.id, dpts[i],additional_attributes=additional_attributes))

        for on in range(self.obstacle_num):
            rt = _RND.choice(routes)
            vehicles.append(_VH(f"OBS_{on}", ObstacleVtype.id, rt.id, dpts[self.VNUM+on],additional_attributes=additional_attributes))

        vehicles.sort(key=lambda v: v.depart_time)

        return vehicles,used_vtypes
    
    def __genPersons(self):
        walks = [self.graph.randomWalk(min_steps=self.MIN_WALKLEN, max_steps=self.MAX_WALKLEN, source_edge_ids=self.source_edge_ids) for i in range(self.N_WALKS)]
        persons:list[_Person] = []
        dpts = [max(_RND.gauss(mu=self.TIME_HORIZON_S*i/self.PNUM,sigma=self.TDEV),0.0) for i in range(self.PNUM)]
        for i in range(self.PNUM):
            pt = Generator.__draw_ptype(self.ptypes)
            persons.append( _Person(id=f"PRS_{i}", depart_time=dpts[i],ptype_id=pt.id) )
        persons.sort(key=lambda p: p.depart_time)
        
        for p in persons:
            wk = _RND.choice(walks)
            p.addWalk(wk)
        return persons

    
    @staticmethod
    def __draw_vtype(vtypes)->_VT:
        r = _RND.random()
        acc = 0.0
        for vt,pp in vtypes:
            acc += pp
            if r <= acc:
                return vt
            
    @staticmethod
    def __draw_ptype(ptypes)->_PT:
        r = _RND.random()
        acc = 0.0
        for pt,pp in ptypes:
            acc += pp
            if r <= acc:
                return pt
    
    @staticmethod
    def __comment(s:str)->str:
        return f"<!-- {s} -->\n"

    
        
    def apply_random_modificators(self,vt:_VT)->_VT:
        nvt = vt.copy()
        for modname,moddata in self.probabilistic_mod_multipliers.items():
            p,mods = moddata
            if _RND.random() <= p:
                for attr,mult in mods.items():
                    if hasattr(nvt.vp,attr):
                        setattr(nvt.vp,attr,getattr(nvt.vp,attr)*mult)
                    elif hasattr(nvt.ip,attr):
                        setattr(nvt.ip,attr,getattr(nvt.ip,attr)*mult)
                nvt.name += f"_{modname}"
        return nvt
    
    def generate(self):

        routes = [self.graph.randomRoute(route_id=f"RT{i}",min_steps=self.MIN_RTLEN,max_steps=self.MAX_RTLEN,source_edge_ids=self.source_edge_ids) for i in range(self.N_ROUTES)]
        vehicles, used_vtypes = self.__gen_vehicles(routes)
        persons = self.__genPersons()

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

            wc("Vehicle and Person Types",tabs=1)
            for vt in used_vtypes:
                f.write(f"\t{vt.xml()}\n")
            for pt,_ in self.ptypes:
                f.write(f"\t{pt.xml()}\n")
            f.write('\n')

            wc("Obstacle vType",tabs=1)
            f.write(f"\t{ObstacleVtype.xml()}\n\n")
            
            a = vehicles + persons
            a.sort(key=lambda x: x.depart_time)
            wc("Vehicles and Pedestrians",tabs=1)
            for vp in a:
                if isinstance(vp, _Person):
                    f.write(f"{vp.xml(tabs=1)}\n")
                else:
                    f.write(f"\t{vp.xml()}\n")
            f.write('\n')

            f.write('</routes>\n')   
        self.num_used_vtypes = len(used_vtypes)

__all__ = ["Generator"]