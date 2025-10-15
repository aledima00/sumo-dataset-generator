from os import path
from genrouter import Graph, IParams, VParams, VClass, Generator, loadPyConfig
import click
import colorama
from colorama import Fore, Style
colorama.init(autoreset=True)


# ==================== GENERATOR PROBABILITY DICTIONARIES ====================

ip_probabs = {
    "NORMAL": (0.5,IParams(speed_factor=1.0, speed_dev=0.1, min_gap_m=2.5)),
    "CAUTIOUS": (0.2,IParams(speed_factor=0.8, speed_dev=0.05, min_gap_m=3.5)),
    "AGGRESSIVE": (0.2,IParams(speed_factor=1.2, speed_dev=0.15, min_gap_m=2.0)),
    "RECKLESS": (0.05,IParams(speed_factor=1.5, speed_dev=0.2, min_gap_m=1.5)),
    "AUTHORIZED": (0.05,IParams(speed_factor=2.0, speed_dev=0.25, min_gap_m=0.5))
}

vp_probabs = {
    "CAR" : (0.55,VParams(accel=2.6, decel=4.5, emergency_decel=9.0, length_m=5.0, max_speed_kmh=180.0)),
    "RACECAR" : (0.02,VParams(accel=4.0, decel=8.0, emergency_decel=13.0, length_m=4.5, max_speed_kmh=300.0)),
    "TRUCK" : (0.07,VParams(accel=1.2, decel=3.5, emergency_decel=7.0, length_m=12.0, max_speed_kmh=120.0)),
    "BUS" : (0.07,VParams(accel=1.5, decel=3.0, emergency_decel=8.0, length_m=10.0, max_speed_kmh=130.0)),
    "MOTORCYCLE" : (0.29,VParams(accel=3.5, decel=5.0, emergency_decel=10.0, length_m=2.5, max_speed_kmh=220.0))
}

vcl_params = {
    "PASSENGER": (0.95,VClass.PASSENGER.value),
    "EMERGENCY": (0.02,VClass.EMERGENCY.value),
    "AUTHORITY": (0.02,VClass.AUTHORITY.value),
    "ARMY": (0.01,VClass.ARMY.value)
}

probabilistic_mod_multipliers={
    "DAMAGED_BRAKES": {"p":0.2, "modifications":{"decel":0.4, "emergency_decel":0.2}},
    "FLAT_TIRE": {"p":0.07, "modifications":{"max_speed_kmh":0.7}},
    "HEAVY_LOAD": {"p":0.1, "modifications":{"accel":0.8, "max_speed_kmh":0.9}},
    "DISTRACTED_DRIVER": {"p":0.1, "modifications":{"speed_factor":0.9, "speed_dev":1.5, "min_gap_m":0.5, "emergency_decel":0.8}}
}

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

def main(gname,time,nroutes,minrtlen,maxrtlen,vnum,tdevp,cfg:str,oname):
    cfgnamepy = cfg if cfg.endswith('.py') else (cfg+'.py' if cfg != '' else DEF_CFGNAMEPY)
    if oname is not None and oname != '':
        oname_rxml = oname if oname.endswith('.rou.xml') else oname+'.rou.xml'
    else:
        oname_rxml = f"{gname}.rou.xml"
    
    FOLDER_PATH = path.join(path.dirname(__file__),"generated",gname)
    IMPORT_PATH = path.join(FOLDER_PATH,cfgnamepy)
    OUTPUT_FILE = path.join(FOLDER_PATH,oname_rxml)

    # ==================== MAP DEFINTION VIA NODES AND EDGES ====================
    try:
        nodes_raw, edges_raw, sources = loadPyConfig(IMPORT_PATH)
    except Exception as e:
        print(f"{Fore.RED}Error loading configuration file {cfgnamepy}:{Style.RESET_ALL}\n{e}")
        return
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
        source_node_ids=sources
    )

    generator.generate()

if __name__ == "__main__":
    main()
