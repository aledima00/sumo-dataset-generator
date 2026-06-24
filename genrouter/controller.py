from pathlib import Path as _Path
import multiprocessing as _mp

from .graph import GraphRepresentation as _GR
from .generator import Generator as _G
from .genopts import GenOptions as _GOPTS
from .sumocfg import SumoCfg as _SCFG


class GenerationController:
    def __init__(self, *, yfname: _Path):
        self.yfname = yfname

    def run(self):
        sumodir = self.yfname.parent.resolve() if self.yfname.is_file() else self.yfname.resolve()
        yf = self.yfname.resolve() if self.yfname.is_file() else (sumodir / "gparams.yaml").resolve()

        options = _GOPTS.fromYaml(yf)
        options.normalizeNullish()

        if options.split > 1:
            nprocs = options.split if (options.split > 0 and options.split <= _mp.cpu_count()) else 1
            opts = options.copy(divide_by=nprocs)
            for i in range(nprocs):
                sdir = sumodir / f"part{i}"
                scfg = _SCFG(sdir / f"cfg.sumocfg", split=options.split)
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

        return {
            "yfname": yf.name,
            "net_file": scfg.net_file.resolve(),
            "time": options.time,
            "steplen": options.steplen,
            "nroutes": options.nroutes,
            "vnum": options.vnum,
        }


__all__ = ["GenerationController"]
