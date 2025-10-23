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
DEF_TIME_HORIZON_S = 200  # seconds
DEF_N_ROUTES = 10
DEF_MIN_RTLEN = 10
DEF_MAX_RTLEN = 20
DEF_VNUM = 100
DEF_TDEV_PROP = 0.1
DEF_ONAME = 'cars.rou.xml'
DEF_OBSTACLES = 0


# ==================== MAIN ====================

@_dc
class Options:
    time: int = DEF_TIME_HORIZON_S
    nroutes: int = DEF_N_ROUTES
    minrtlen: int = DEF_MIN_RTLEN
    maxrtlen: int = DEF_MAX_RTLEN
    vnum: int = DEF_VNUM
    tdevp: float = DEF_TDEV_PROP
    oname: str = DEF_ONAME
    obstacles: int = DEF_OBSTACLES

    def __init__(self,**kwargs):
        for k,v in kwargs.items():
            setattr(self,k,v)
        if not self.oname.endswith('.rou.xml'):
            self.oname = self.oname + '.rou.xml'

    @staticmethod
    def fromYaml(yaml_path:_Path)->'Options':
        if (not yaml_path.exists()) or (not yaml_path.is_file()):
            return Options()
        with open(yaml_path,'r') as yf:
            options_dict:dict = yaml.safe_load(yf)
        return Options(**options_dict)
    
    def dump(self,yaml_path:_Path):
        options_dict = _asdict(self)
        with open(yaml_path,'w') as yf:
            yaml.dump(options_dict,yf,default_flow_style=False,allow_unicode=True)

    def overwriteWith(self,**kwargs):
        for k,v in kwargs.items():
            if v is not None and (type(v) is not str or v != ''):
                setattr(self,k,v)

    
def getConsole(ip_probabs:dict,vp_probabs:dict,vcl_params:dict,probabilistic_mod_multipliers:dict):

    @click.command()
    @click.argument('sumocfg_path', required=True, type=click.Path(exists=True, dir_okay=False), nargs=1)
    @click.option('--time', type=int, default=None, help=f'Time horizon in seconds (default: {DEF_TIME_HORIZON_S}s)')
    @click.option('--nroutes',type=int, default=None, help=f'Number of routes to generate (default: {DEF_N_ROUTES})')
    @click.option('--minrtlen', type=int, default=None, help=f'Minimum route length in number of edges (default: {DEF_MIN_RTLEN})')
    @click.option('--maxrtlen', type=int, default=None, help=f'Maximum route length in number of edges (default: {DEF_MAX_RTLEN})')
    @click.option('--vnum', type=int, default=None, help=f'Number of vehicles to generate (default: {DEF_VNUM})')
    @click.option('--tdevp', type=float, default=None, help=f'Time deviation as proportion of time horizon (default: {DEF_TDEV_PROP})')
    @click.option('--oname',type=str, default=None, help='Name of the output .rou.xml file (default: same as generator name)')
    @click.option('--obstacles',type=int, default=None,help='Number of obstacle vehicles to generate (default: 0)')
    @click.option('--save-gparams',is_flag=True,help='If set, saves the generation parameters to a gparams.yaml file in the cwd.')
    def console(sumocfg_path,time,nroutes,minrtlen,maxrtlen,vnum,tdevp,oname,obstacles:int,save_gparams:bool):

        scfg = _SCFG(_Path(sumocfg_path))
        yf = _Path(os.getcwd()).resolve() / "gparams.yaml"

        options = Options.fromYaml(yf)
        options.overwriteWith(
            time=time,
            nroutes=nroutes,
            minrtlen=minrtlen,
            maxrtlen=maxrtlen,
            vnum=vnum,
            tdevp=tdevp,
            oname=oname,
            obstacles=obstacles
        )
        if save_gparams:
            options.dump(yf)
        g = _GR(netfile=scfg.net_file)
        generator = Generator(
            OUTPUT_FILE=str(scfg.routes_file),
            TIME_HORIZON_S=options.time,
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
