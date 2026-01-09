from pathlib import Path as _Path
from .graph import GraphRepresentation as _GR
from .generator import Generator as _G
from .genopts import GenOptions as _GOPTS
from .sumocfg import SumoCfg as _SCFG
import click as _clk
import multiprocessing as _mp
from colorama import Fore as _Fore, Style as _Style


@_clk.command()
@_clk.argument('yfname', required=True, type=_clk.Path(exists=True, dir_okay=True, file_okay=True, path_type=_Path))
def generate(yfname:_Path):

    try:
        sumodir = yfname.parent.resolve() if yfname.is_file() else yfname.resolve()
        yf = yfname.resolve() if yfname.is_file() else (sumodir / "gparams.yaml").resolve()


        options = _GOPTS.fromYaml(yf)
        options.normalizeNullish()
        _clk.echo(f"{_Fore.CYAN}[generation parameters loaded from './{yf.name}']{_Style.RESET_ALL}")

        if options.split:
            nprocs = _mp.cpu_count() // 2
            opts = options.copy(divide_by=nprocs)
            for i in range(nprocs):
                sdir = sumodir / f"part{i}"
                scfg = _SCFG(sdir/ f"cfg.sumocfg", split=True)
                scfg.overwrite(
                    time=opts.time,
                    step_len=opts.steplen
                )
                scfg.checkReqParams()
                scfg.save()

                g = _GR(netfile=scfg.net_file)
                generator = _G(
                    OUTPUT_FILE=scfg.routes_file,
                    TIME_HORIZON_S=scfg.duration_s,
                    gparams=opts,
                    graph=g,
                )

                generator.generate()
        else:
            sdir = sumodir
            scfg = _SCFG(sdir / "cfg.sumocfg")
            scfg.overwrite(
                time=options.time,
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
            #TODO: add output routes file
            ("INPUT NETWORK FILE", scfg.net_file.resolve()),
            ("TOTAL SIMULATION TIME (S)", options.time),
            ("SIMULATION STEP LENGTH (S)", options.steplen),
            ("NUM. OF ROUTES", options.nroutes),
            ("NUM. OF WALKS", options.nwalks),
            ("NUM. OF OBSTACLES", options.obstacles),
            ("NUM. OF VEHICLES", options.vnum),
            ("NUM. OF PEDESTRIANS", options.pnum),
            #TODO: add num. of unique vtypes
        ]
        _clk.echo(f"{_Fore.GREEN}Generation completed successfully!{_Style.RESET_ALL}"+"".join([f"\n{_Fore.YELLOW}  - {k}{_Style.RESET_ALL}: {v}" for k,v in prints]))
    except Exception as e:
        _clk.echo(f"{_Fore.RED}Error during generation{_Style.RESET_ALL}:\n{e}")
        raise

__all__ = ["generate"]
