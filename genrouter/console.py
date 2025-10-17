from pathlib import Path
from .graph import Graph
from .generator import Generator
from .loadConfig import loadPyConfig
import click
from colorama import Fore, Style

# ==================== FINAL GENERATION PARAMETERS ====================

# default generation params
DEF_TIME_HORIZON_S = 200  # seconds
DEF_N_ROUTES = 10
DEF_MIN_RTLEN = 10
DEF_MAX_RTLEN = 20
DEF_VNUM = 100
DEF_TDEV_PROP = 0.1
DEF_CFGNAMEPY = "gcfg.py"
DEF_ONAME = None


# ==================== MAIN ====================

def getConsole(ip_probabs:dict,vp_probabs:dict,vcl_params:dict,probabilistic_mod_multipliers:dict):

    @click.command()
    @click.option('--gname', help='Name of the generator (also the folder name in /generated/)', required=True)
    @click.option('--time', default=DEF_TIME_HORIZON_S, help=f'Time horizon in seconds (default: {DEF_TIME_HORIZON_S}s)')
    @click.option('--nroutes', default=DEF_N_ROUTES, help=f'Number of routes to generate (default: {DEF_N_ROUTES})')
    @click.option('--minrtlen', default=DEF_MIN_RTLEN, help=f'Minimum route length in number of edges (default: {DEF_MIN_RTLEN})')
    @click.option('--maxrtlen', default=DEF_MAX_RTLEN, help=f'Maximum route length in number of edges (default: {DEF_MAX_RTLEN})')
    @click.option('--vnum', default=DEF_VNUM, help=f'Number of vehicles to generate (default: {DEF_VNUM})')
    @click.option('--tdevp', default=DEF_TDEV_PROP, help=f'Time deviation as proportion of time horizon (default: {DEF_TDEV_PROP})')
    @click.option('--cfg', default=DEF_CFGNAMEPY, help=f'Name of the python configuration file in the generator folder (default: {DEF_CFGNAMEPY})')
    @click.option('--oname',default=DEF_ONAME, help='Name of the output .rou.xml file (default: same as generator name)')
    @click.option('--obstacles',default=0,help='Number of obstacle vehicles to generate (default: 0)')
    def console(gname,time,nroutes,minrtlen,maxrtlen,vnum,tdevp,cfg:str,oname,obstacles:int):
        cfgnamepy = cfg if cfg.endswith('.py') else (cfg+'.py' if cfg != '' else DEF_CFGNAMEPY)
        if oname is not None and oname != '':
            oname_rxml = oname if oname.endswith('.rou.xml') else oname+'.rou.xml'
        else:
            oname_rxml = f"{gname}.rou.xml"
        
        FOLDER_PATH = Path(__file__).parent.parent / "generated" / gname
        IMPORT_PATH = FOLDER_PATH / cfgnamepy
        OUTPUT_FILE = FOLDER_PATH / oname_rxml

        # ==================== MAP DEFINTION VIA NODES AND EDGES ====================
        try:
            nodes_raw, edges_raw, sources = loadPyConfig(IMPORT_PATH)
        except Exception as e:
            raise Exception(f"{Fore.RED}Error loading configuration file {cfgnamepy}:{Style.RESET_ALL}\n{e}")
        g = Graph()
        g.addRawNodes(nodes_raw)
        g.addRawEdges(edges_raw)
        generator = Generator(
            OUTPUT_FILE=OUTPUT_FILE,
            TIME_HORIZON_S=time,
            N_ROUTES=nroutes,
            MIN_RTLEN=minrtlen,
            MAX_RTLEN=maxrtlen,
            VNUM=vnum,
            TDEV_PROP=tdevp,
            ip_probabs=ip_probabs,
            vp_probabs=vp_probabs,
            vcl_params=vcl_params,
            graph=g,
            probabilistic_mod_multipliers=probabilistic_mod_multipliers,
            source_node_ids=sources,
            obstacle_num=obstacles
        )

        gen_out = generator.generate()
        click.echo(f"{Fore.GREEN}Generation completed successfully!{Style.RESET_ALL}"+"".join([f"\n   {Fore.YELLOW}- {k}{Fore.RESET}: {v}" for k,v in gen_out.items()]))

    return console
