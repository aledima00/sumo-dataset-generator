from pathlib import Path as _Path
from .graph import GraphRepresentation as _GR
from .generator import Generator
import click
from colorama import Fore, Style
import yaml
import os
from dataclasses import dataclass as _dc, asdict as _asdict
from .sumocfg import SumoCfg as _SCFG

# ==================== FINAL GENERATION PARAMETERS ====================

# default generation params
DEF_N_ROUTES = 10
DEF_MIN_RTLEN = 10
DEF_MAX_RTLEN = 20
DEF_VNUM = 100
DEF_TDEV_PROP = 0.1
DEF_OBSTACLES = 0


# ==================== MAIN ====================

@_dc
class GenOptions:
    nroutes: int = DEF_N_ROUTES
    minrtlen: int = DEF_MIN_RTLEN
    maxrtlen: int = DEF_MAX_RTLEN
    vnum: int = DEF_VNUM
    tdevp: float = DEF_TDEV_PROP
    obstacles: int = DEF_OBSTACLES

    @staticmethod
    def fromYaml(yaml_path:_Path)->'GenOptions':
        if (not yaml_path.exists()) or (not yaml_path.is_file()):
            return GenOptions()
        with open(yaml_path,'r') as yf:
            options_dict:dict = yaml.safe_load(yf)
        return GenOptions(**options_dict)
    
    def dump(self,yaml_path:_Path):
        options_dict = _asdict(self)
        with open(yaml_path,'w') as yf:
            yaml.dump(options_dict,yf,default_flow_style=False,allow_unicode=True)

    def overwriteWith(self,**kwargs):
        for k,v in kwargs.items():
            if v is not None and (type(v) is not str or v != ''):
                setattr(self,k,v)

def checkRequiredParam(param):
    if param is None:
        raise ValueError(f"Required parameter '{param}' not specified nor present in SUMO config file!")
    
def getConsole(ip_probabs:dict,vp_probabs:dict,vcl_params:dict,probabilistic_mod_multipliers:dict):

    @click.command()
    @click.argument('sumocfg_path', required=True, type=click.Path(exists=True, dir_okay=False), nargs=1)
    @click.option('--time', type=int, default=None, help=f'Time horizon in seconds (default: from SUMO config file). If specified, will override the one in the SUMO config file.')
    @click.option('--route-filename',type=str, default=None, help=f'Output route filename (default: from SUMO config file). If specified, will override the one in the SUMO config file.')
    @click.option('--net-filename',type=str, default=None, help=f'Input network filename (default: from SUMO config file). If specified, will override the one in the SUMO config file.')
    @click.option('--nroutes',type=int, default=None, help=f'Number of routes to generate (default: {DEF_N_ROUTES})')
    @click.option('--minrtlen', type=int, default=None, help=f'Minimum route length in number of edges (default: {DEF_MIN_RTLEN})')
    @click.option('--maxrtlen', type=int, default=None, help=f'Maximum route length in number of edges (default: {DEF_MAX_RTLEN})')
    @click.option('--vnum', type=int, default=None, help=f'Number of vehicles to generate (default: {DEF_VNUM})')
    @click.option('--tdevp', type=float, default=None, help=f'Time deviation as proportion of time horizon (default: {DEF_TDEV_PROP})')
    @click.option('--obstacles',type=int, default=None,help='Number of obstacle vehicles to generate (default: 0)')
    @click.option('--save-gparams',is_flag=True,help='If set, saves the generation parameters to a gparams.yaml file in the cwd.')
    def console(sumocfg_path,time,nroutes,minrtlen,maxrtlen,vnum,tdevp,route_filename,net_filename,obstacles:int,save_gparams:bool):

        scfg = _SCFG(_Path(sumocfg_path))
        if time is not None:
            scfg.duration_s = time
        else: 
            checkRequiredParam(scfg.duration_s)
        if route_filename is not None:
            scfg.routes_file = _Path(route_filename).resolve()
        else:
            checkRequiredParam(scfg.routes_file)
        if net_filename is not None:
            scfg.net_file = _Path(net_filename).resolve()
        else:
            checkRequiredParam(scfg.net_file)

        scfg.save()
        
        yf = _Path(os.getcwd()).resolve() / "gparams.yaml"

        options = GenOptions.fromYaml(yf)
        options.overwriteWith(
            nroutes=nroutes,
            minrtlen=minrtlen,
            maxrtlen=maxrtlen,
            vnum=vnum,
            tdevp=tdevp,
            obstacles=obstacles
        )
        if save_gparams:
            options.dump(yf)
        g = _GR(netfile=scfg.net_file)
        generator = Generator(
            OUTPUT_FILE=str(scfg.routes_file),
            TIME_HORIZON_S=scfg.duration_s,
            N_ROUTES=options.nroutes,
            MIN_RTLEN=options.minrtlen,
            MAX_RTLEN=options.maxrtlen,
            VNUM=options.vnum,
            TDEV_PROP=options.tdevp,
            ip_probabs=ip_probabs,
            vp_probabs=vp_probabs,
            vcl_params=vcl_params,
            graph=g,
            probabilistic_mod_multipliers=probabilistic_mod_multipliers,
            obstacle_num=options.obstacles
        )

        gen_out = generator.generate()
        click.echo(f"{Fore.GREEN}Generation completed successfully!{Style.RESET_ALL}"+"".join([f"\n   {Fore.YELLOW}- {k}{Fore.RESET}: {v}" for k,v in gen_out.items()]))
        if save_gparams:
            click.echo(f"{Fore.CYAN}[generation parameters saved to '{yf.parts[-1]}']{Style.RESET_ALL}")
    return console
