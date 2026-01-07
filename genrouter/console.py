from pathlib import Path as _Path
from .graph import GraphRepresentation as _GR
from .generator import Generator as _G
from .genopts import GenOptions as _GOPTS
from .sumocfg import SumoCfg as _SCFG
import click as _clk
from colorama import Fore as _Fore, Style as _Style
    
def _shortenPath(p:_Path)->str:
    return str(p if len(p.parts)<=4 else _Path(p.parts[0], p.parts[1], "...", p.parts[-2], p.parts[-1]))

@_clk.command()
@_clk.option('-P', '--sumocfg-path', required=True, type=_clk.Path(exists=True, dir_okay=False))
@_clk.option('--gparams-yaml-fname', '-Y', 'gparams_fname', type=_clk.Path(exists=True, dir_okay=False, file_okay=True), default=None, help='Path to the YAML file containing generation parameters (default: in sumodir). The file contains generation paramters in YAML format. If present, CLI-provided parameters will override the parameters in the file.')
def generate(sumocfg_path,gparams_fname):

    try:
        sumodir = _Path(sumocfg_path).resolve().parent

        yf = sumodir / "gparams.yaml" if gparams_fname is None else _Path(str(gparams_fname)).resolve()

        options = _GOPTS.fromYaml(yf)
        options.normalizeNullish()
        _clk.echo(f"{_Fore.CYAN}[generation parameters loaded from './{yf.name}']{_Style.RESET_ALL}")

        scfg = _SCFG(_Path(sumocfg_path))
        scfg.overwrite(
            time=options.time,
            route_filename=route_filename,
            net_filename=net_filename,
            step_len=options.steplen
        )
        scfg.checkReqParams()
        scfg.save()

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
            ("NUM. OF WALKS", options.nwalks),
            ("NUM. OF OBSTACLES", options.obstacles),
            ("NUM. OF VEHICLES", options.vnum),
            ("NUM. OF PEDESTRIANS", options.pnum),
            ("NUM. OF UNIQUE VTYPEs", generator.num_used_vtypes)
        ]
        _clk.echo(f"{_Fore.GREEN}Generation completed successfully!{_Style.RESET_ALL}"+"".join([f"\n{_Fore.YELLOW}  - {k}{_Style.RESET_ALL}: {v}" for k,v in prints]))
    except Exception as e:
        _clk.echo(f"{_Fore.RED}Error during generation{_Style.RESET_ALL}:\n{e}")

__all__ = ["generate"]
