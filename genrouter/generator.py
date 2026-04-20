from .graph import GraphRepresentation as _GR
from .vehicles import VType as _VT, Vehicle as _VH
from .genopts import GenOptions as _GenOptions

import random as _RND
from pathlib import Path as _Path

def boundvalue(v,minv,maxv):
    return max(minv, min(v, maxv))

additional_attributes={
    "departLane":"allowed",
    "departPos":"base",
    "departSpeed":"random",
    "departPosLat":"random",
    "arrivalLane":"current",
    "arrivalPos":"max",
    "arrivalSpeed":"current",
    #"arrivalPosLat":"default",
    "insertionChecks":"none"
}

class Generator:
    def __init__(self,*,gparams:_GenOptions,OUTPUT_FILE:_Path,TIME_HORIZON_S:int,graph:_GR):
        self.OUTPUT_FILE = OUTPUT_FILE
        self.TIME_HORIZON_S = TIME_HORIZON_S
        self.N_ROUTES = gparams.nroutes
        self.MIN_RTLEN = gparams.minrtlen
        self.MAX_RTLEN = gparams.maxrtlen
        self.VNUM = gparams.vnum
        self.vdraw_method = gparams.VDrawMethod()
        self.ip_probabs = gparams.IPDict()
        self.vp_probabs = gparams.VPDict()
        self.vcl_probabs = gparams.VCLDict()
        self.prs_params = gparams.PPDict()
        self.modifiers = gparams.ModDict()
        # print(f"modifiers: {self.modifiers}")
        self.steplen= gparams.steplen
        self.source_edge_ids = gparams.source_edges
        self.vtypes = self.__gen_vtypes()
        self.graph = graph
        self.num_used_vtypes = 0
    
    def __gen_vtypes(self):
        vtypes = []
        for ipn,(ipp,ip) in self.ip_probabs.items():
            for vpn,(vpp,vp) in self.vp_probabs.items():
                for vcln,(vclp,vcl) in self.vcl_probabs.items():
                    vtypes.append( (_VT(name=f"{vpn}_{ipn}_{vcln}", vp=vp, ip=ip, vcl=vcl,additional_attributes=additional_attributes), ipp*vpp*vclp))
        return vtypes
    
    def __gen_vehicles(self):
        routes = [self.graph.randomRoute(route_id=f"RT{i}",min_steps=self.MIN_RTLEN,max_steps=self.MAX_RTLEN,source_edge_ids=self.source_edge_ids) for i in range(self.N_ROUTES)]
        # shuffle to ensure randomness
        _RND.shuffle(routes)
                
        used_routes = set()
        used_vtypes = set()

        vehicles:list[_VH] = []
        dpts = self.vdraw_method.generateDepartures(self.VNUM, self.TIME_HORIZON_S, shuffle=True)

        for i in range(self.VNUM):
            vt = Generator.__draw_vtype(self.vtypes)
            vt = self.apply_random_modificators(vt)
            used_vtypes.add(vt)
            rt = routes[i % len(routes)]
            used_routes.add(rt)
            vehicles.append(_VH(f"veh{i}", vt.id, rt.id, dpts[i],additional_attributes=additional_attributes))

        vehicles.sort(key=lambda v: v.depart_time)

        return vehicles,used_vtypes,used_routes

    
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
        nvt = vt.copy()
        for modname,moddata in self.modifiers.items():
            p,mods = moddata
            if _RND.random() <= p:
                match modname:
                    case "DISTRACTED_DRIVER":
                        reactionTimeAvg = mods.get("reactionTimeAvg",None)
                        reactionTimeDev = mods.get("reactionTimeDev",None)
                        if reactionTimeAvg is not None and reactionTimeDev is not None:
                            reactionTime = max(self.steplen,_RND.gauss(reactionTimeAvg,reactionTimeDev))
                            #TODO:CHECK if it is better to directly provide the new value instead of a multiplier
                            nvt.ip.setActionStepLength(reactionTime)
                    case "UNEXPECTED_DECEL":
                        decelPropAvg = mods.get("decelPropAvg",None)
                        decelPropDev = mods.get("decelPropDev",None)
                        if decelPropAvg is not None and decelPropDev is not None:
                            decelProp = boundvalue(_RND.gauss(decelPropAvg,decelPropDev),0.0,1.0)
                            nvt.vp.apparent_decel = nvt.vp.decel * decelProp
                            # apparent decel is different than decel!!
                    case _:
                        raise ValueError(f"Unknown modificator: {modname}")
                nvt.name += f"_{modname}"
        return nvt
    
    def generate(self):

        vehicles, used_vtypes, routes = self.__gen_vehicles()

        with open (self.OUTPUT_FILE,'w') as f:
            def wc(s,*,tabs=0):
                f.write(f"{'\t'*tabs}{Generator.__comment(s)}")
            wc(f"Generated vehicle file: {self.N_ROUTES} routes, {self.VNUM} vehicles")
            wc(f">> {self.N_ROUTES} routes, each {self.MIN_RTLEN} to {self.MAX_RTLEN} edges long")
            wc(f">> {self.VNUM} vehicles")
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
            
            a = vehicles
            a.sort(key=lambda x: x.depart_time)
            wc("Vehicles",tabs=1)
            for vp in a:
                f.write(f"\t{vp.xml()}\n")
            f.write('\n')

            f.write('</routes>\n')   
        self.num_used_vtypes = len(used_vtypes)

__all__ = ["Generator"]