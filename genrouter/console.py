from pathlib import Path as _Path
from .graph import GraphRepresentation as _GR
from .generator import Generator as _G
from .genopts import GenOptions as _GOPTS
from .sumocfg import SumoCfg as _SCFG
import click as _clk
from colorama import Fore as _Fore, Style as _Style
import os as _os
    
def _shortenPath(p:_Path)->str:
    return str(p if len(p.parts)<=4 else _Path(p.parts[0], p.parts[1], "...", p.parts[-2], p.parts[-1]))

_defopts = _GOPTS()

@_clk.command()
@_clk.argument('sumocfg_path', required=True, type=_clk.Path(exists=True, dir_okay=False), nargs=1)
@_clk.option('--time', type=int, default=None, help=f'Time horizon in seconds (default: from SUMO config file). If specified, will override the one in the SUMO config file.')
@_clk.option('--route-filename',type=str, default=None, help=f'Output route filename (default: from SUMO config file). If specified, will override the one in the SUMO config file.')
@_clk.option('--net-filename',type=str, default=None, help=f'Input network filename (default: from SUMO config file). If specified, will override the one in the SUMO config file.')
@_clk.option('--step-len', type=float, default=None, help='Simulation step length in seconds (default: from SUMO config file). If specified, will override the one in the SUMO config file.')
@_clk.option('--nroutes',type=int, default=None, help=f'Number of routes to generate (default: {_defopts.nroutes})')
@_clk.option('--nwalks',type=int, default=None, help=f'Number of walking routes to generate (default: {_defopts.nwalks})')
@_clk.option('--minrtlen', type=int, default=None, help=f'Minimum route length in number of edges (default: {_defopts.minrtlen})')
@_clk.option('--maxrtlen', type=int, default=None, help=f'Maximum route length in number of edges (default: {_defopts.maxrtlen})')
@_clk.option('--minwalklen', type=int, default=None, help=f'Minimum walking route length in number of edges (default: {_defopts.minwalklen})')
@_clk.option('--maxwalklen', type=int, default=None, help=f'Maximum walking route length in number of edges (default: {_defopts.maxwalklen})')
@_clk.option('--vnum', type=int, default=None, help=f'Number of vehicles to generate (default: {_defopts.vnum})')
@_clk.option('--pnum', type=int, default=None, help=f'Number of pedestrians to generate (default: {_defopts.pnum})')
@_clk.option('--tdevp', type=float, default=None, help=f'Time deviation as proportion of time horizon (default: {_defopts.tdevp})')
@_clk.option('--obstacles',type=int, default=None,help='Number of obstacle vehicles to generate (default: 0)')
def generate(sumocfg_path,time,nroutes,nwalks,step_len,minrtlen,maxrtlen,minwalklen,maxwalklen,vnum,pnum,tdevp,route_filename,net_filename,obstacles:int):

    try:
        scfg = _SCFG(_Path(sumocfg_path))
        scfg.overwrite(
            time=time,
            route_filename=route_filename,
            net_filename=net_filename,
            step_len=step_len
        )
        scfg.checkReqParams()
        scfg.save()

        yf = _Path(_os.getcwd()).resolve() / "gparams.yaml"
        yf2 = _Path(_os.getcwd()).resolve()/ "gparams-compiled.yaml"

        options = _GOPTS.fromYaml(yf)
        options.overwriteWith(
            nroutes=nroutes,
            minrtlen=minrtlen,
            maxrtlen=maxrtlen,
            vnum=vnum,
            tdevp=tdevp,
            obstacles=obstacles
        )
        options.dump(yf2)
        _clk.echo(f"{_Fore.CYAN}[generation parameters saved to './{yf.name}']{_Style.RESET_ALL}")
        g = _GR(netfile=scfg.net_file)
        generator = _G(
            OUTPUT_FILE=scfg.routes_file,
            TIME_HORIZON_S=scfg.duration_s,
            gparams=options,
            graph=g,
        )

        generator.generate()
        prints = [
            ("OUTPUT ROUTE FILE", _shortenPath(scfg.routes_file)),
            ("INPUT NETWORK FILE", _shortenPath(scfg.net_file)),
            ("TOTAL SIMULATION TIME (S)", scfg.duration_s),
            ("SIMULATION STEP LENGTH (S)", scfg.step_length_s),
            ("NUM. OF ROUTES", options.nroutes),
            ("NUM. OF OBSTACLES", options.obstacles),
            ("NUM. OF VEHICLES", options.vnum),
            ("NUM. OF UNIQUE VTYPEs", generator.num_used_vtypes)
        ]
        _clk.echo(f"{_Fore.GREEN}Generation completed successfully!{_Style.RESET_ALL}"+"".join([f"\n{_Fore.YELLOW}  - {k}{_Style.RESET_ALL}: {v}" for k,v in prints]))
    except Exception as e:
        _clk.echo(f"{_Fore.RED}Error during generation{_Style.RESET_ALL}:\n{e}")

__all__ = ["generate"]
