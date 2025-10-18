from pathlib import Path
from .graph import Graph
from .generator import Generator
from .loadConfig import loadPyConfig
import click
from colorama import Fore, Style
import yaml
import os
from dataclasses import dataclass, asdict

# ==================== FINAL GENERATION PARAMETERS ====================

# default generation params
DEF_TIME_HORIZON_S = 200  # seconds
DEF_N_ROUTES = 10
DEF_MIN_RTLEN = 10
DEF_MAX_RTLEN = 20
DEF_VNUM = 100
DEF_TDEV_PROP = 0.1
DEF_CFGNAMEPY = "gcfg.py"
DEF_OBSTACLES = 0


# ==================== MAIN ====================

@dataclass
class Options:
    gname: str
    time: int = DEF_TIME_HORIZON_S
    nroutes: int = DEF_N_ROUTES
    minrtlen: int = DEF_MIN_RTLEN
    maxrtlen: int = DEF_MAX_RTLEN
    vnum: int = DEF_VNUM
    tdevp: float = DEF_TDEV_PROP
    cfg: str = DEF_CFGNAMEPY
    oname: str = None
    obstacles: int = DEF_OBSTACLES

    def __init__(self,gname,**kwargs):
        self.gname = gname
        for k,v in kwargs.items():
            setattr(self,k,v)
        if self.oname is None or self.oname == '':
            self.oname = f"{gname}.rou.xml"
        elif not self.oname.endswith('.rou.xml'):
            self.oname = self.oname + '.rou.xml'
        if self.cfg == '':
            self.cfg = DEF_CFGNAMEPY
        elif not self.cfg.endswith('.py'):
            self.cfg = self.cfg + '.py'

    @staticmethod
    def fromYaml(yaml_path:Path,*,gname:str)->'Options':
        if (not yaml_path.exists()) or (not yaml_path.is_file()):
            return Options(gname)
        with open(yaml_path,'r') as yf:
            options_dict:dict = yaml.safe_load(yf)
            if options_dict.get('gname',None) is not None:
                del options_dict['gname']
        return Options(gname,**options_dict)
    
    def dump(self,yaml_path:Path):
        options_dict = asdict(self)
        del options_dict['gname']
        if self.oname == f"{self.gname}.rou.xml":
            del options_dict['oname']
        with open(yaml_path,'w') as yf:
            yaml.dump(options_dict,yf,default_flow_style=False,allow_unicode=True)

    def overwriteWith(self,**kwargs):
        for k,v in kwargs.items():
            if v is not None and (type(v) is not str or v != ''):
                setattr(self,k,v)

    
def getConsole(ip_probabs:dict,vp_probabs:dict,vcl_params:dict,probabilistic_mod_multipliers:dict):

    @click.command()
    @click.argument('gname', required=True)
    @click.option('--time', type=int, default=None, help=f'Time horizon in seconds (default: {DEF_TIME_HORIZON_S}s)')
    @click.option('--nroutes',type=int, default=None, help=f'Number of routes to generate (default: {DEF_N_ROUTES})')
    @click.option('--minrtlen', type=int, default=None, help=f'Minimum route length in number of edges (default: {DEF_MIN_RTLEN})')
    @click.option('--maxrtlen', type=int, default=None, help=f'Maximum route length in number of edges (default: {DEF_MAX_RTLEN})')
    @click.option('--vnum', type=int, default=None, help=f'Number of vehicles to generate (default: {DEF_VNUM})')
    @click.option('--tdevp', type=float, default=None, help=f'Time deviation as proportion of time horizon (default: {DEF_TDEV_PROP})')
    @click.option('--cfg', type=str, default=None, help=f'Name of the python configuration file in the generator folder (default: {DEF_CFGNAMEPY})')
    @click.option('--oname',type=str, default=None, help='Name of the output .rou.xml file (default: same as generator name)')
    @click.option('--obstacles',type=int, default=None,help='Number of obstacle vehicles to generate (default: 0)')
    @click.option('--save-gparams',is_flag=True,help='If set, saves the generation parameters to a gparams.yaml file in the cwd.')
    def console(gname,time,nroutes,minrtlen,maxrtlen,vnum,tdevp,cfg:str,oname,obstacles:int,save_gparams:bool):
        yf = Path(os.getcwd()).resolve() / "gparams.yaml"
        options = Options.fromYaml(yf,gname=gname)
        options.overwriteWith(
            time=time,
            nroutes=nroutes,
            minrtlen=minrtlen,
            maxrtlen=maxrtlen,
            vnum=vnum,
            tdevp=tdevp,
            cfg=cfg,
            oname=oname,
            obstacles=obstacles
        )
        if save_gparams:
            options.dump(yf)
        
        FOLDER_PATH = Path(__file__).parent.parent / "generated" / gname
        IMPORT_PATH = FOLDER_PATH / options.cfg
        OUTPUT_FILE = FOLDER_PATH / options.oname

        # ==================== MAP DEFINTION VIA NODES AND EDGES ====================
        try:
            nodes_raw, edges_raw, sources = loadPyConfig(IMPORT_PATH)
        except Exception as e:
            raise Exception(f"{Fore.RED}Error loading configuration file {options.cfg}:{Style.RESET_ALL}\n{e}")
        g = Graph()
        g.addRawNodes(nodes_raw)
        g.addRawEdges(edges_raw)
        generator = Generator(
            OUTPUT_FILE=OUTPUT_FILE,
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
            source_node_ids=sources,
            obstacle_num=options.obstacles
        )

        gen_out = generator.generate()
        click.echo(f"{Fore.GREEN}Generation completed successfully!{Style.RESET_ALL}"+"".join([f"\n   {Fore.YELLOW}- {k}{Fore.RESET}: {v}" for k,v in gen_out.items()]))
        if save_gparams:
            click.echo(f"{Fore.CYAN}[generation parameters saved to '{yf.parts[-1]}']{Style.RESET_ALL}")

    return console
