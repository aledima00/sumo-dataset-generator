import click as _click
from math import floor as _floor
import sumolib as _sumolib
import traci as _traci
from enum import Enum as _EN
from pathlib import Path as _Path
from .labels import LabelsEnum as _LE, MultiLabel as _MLB
from .pack import Frame as _Frame, StaticPackAnalyzer as _SPA
from .vehicle import _Vehicle as _Vehicle
from colorama import Fore as _Fore, Style as _Style
import re as _re
import shutil as _sh

class CollisionAction(_EN):
    TELEPORT = "teleport"
    WARN = "warn"
    NONE = "none"
    REMOVE = "remove"


class TraciController:
    plabels:list[_MLB]=[]
    def __init__(self,*,gui:bool,cfg_path:str,step_len:float,frame_pack_size:int,sim_time_s:float,on_collision:CollisionAction,warnings:bool):
        self.gui = gui
        self.cfg_path = _Path(cfg_path).resolve()
        self.step_len = step_len
        self.frame_pack_size = frame_pack_size
        self.sim_time_s = sim_time_s
        self.on_collision = on_collision
        self.warnings = warnings

        self.sumobin = _sumolib.checkBinary('sumo-gui' if gui else 'sumo')
        self.total_steps = _floor(self.sim_time_s / self.step_len)
        self.total_packs = _floor(self.total_steps / self.frame_pack_size)


    def run(self):
        _traci.start([
            self.sumobin,
            "-c", self.cfg_path,
            "--collision.action", self.on_collision.value,
            "--no-warnings", "false" if self.warnings else "true",
            "--start"
        ])
        for pn in range(self.total_packs):
            pack: list[_Frame] = []
            lb = _MLB()

            for fn in range(self.frame_pack_size):
                _traci.simulationStep()
                # CHECK LABEL COL
                if not lb.checkLabel(_LE.COLLISION):
                    clist = _traci.simulation.getCollidingVehiclesIDList()
                    if len(clist)>0:
                        lb.setLabel(_LE.COLLISION)

                # frame creation and push
                frame = _Frame()
                for vid in _traci.vehicle.getIDList(): 
                    if str(vid).startswith("OBS_"):
                        frame.obstacles[vid] = _Vehicle.from_traci(vid)
                    else:
                        frame.vehicles[vid] = _Vehicle.from_traci(vid)

                pack.append(frame)
        
            sp_analyzer = _SPA(pack, lb)
            lb = sp_analyzer.analyze()
            self.plabels.append(lb)
        
        _traci.close() 

    def dumpExpanded(self, filepath:_Path):
        with open(filepath.resolve(), "w") as fv:
            fv.write("PackId, " + ", ".join([label.name for label in _LE]) + "\n")
            for pn, lb in enumerate(self.plabels):
                fv.write(f"P{pn}, " + ", ".join(map(lambda x: "1" if x else "0", lb.getExpanded())) + "\n")


    def dumpEncoded(self, filepath:_Path):
        with open(filepath.resolve(), "w") as fe:
            fe.write("PackId, MLBEncoded\n")
            for pn, lb in enumerate(self.plabels):
                fe.write(f"P{pn}, {lb.getEncoded()}\n")

    def dumpVerbose(self, filepath:_Path):
        with open(filepath.resolve(), "w") as fv:
            fv.write("PackId, Labels\n")
            for pn, lb in enumerate(self.plabels):
                fv.write(f"P{pn}, " + ", ".join(lb.getLabels(short=True)) + "\n")

        



@_click.command()
@_click.option('--gui','-g', is_flag=True, default=False, help='Run SUMO with GUI')
@_click.option('--no-warnings', is_flag=True, default=False, help='Suppress SUMO warnings.')
@_click.option('--step-len','-s', type=float, default=0.2, help='Length of each simulation step in seconds (default: 0.2s).')
@_click.option('--pack-size','-p', type=int, default=20, help='Number of frames in each pack (default: 20).')
@_click.option('--sim-time','-t', type=float, default=500.0, help='Total simulation time in seconds (default: 500s).')
@_click.option('--on-collision', type=_click.Choice([e.value for e in CollisionAction]), default=CollisionAction.TELEPORT.value, help='Action to take on collision (default: remove).')
@_click.option('-om', '--output-mode', 'output_mode', type=str, default='e', help='Output mode for pack labels: combination of [e]ncoded, [x]panded, [v]erbose (default: [e]).')
@_click.option('--outdir', type=_click.Path(file_okay=False, dir_okay=True, writable=True), default=None, help='Output directory for label files (default: ./plabels).')
@_click.argument('cfg_path', type=_click.Path(exists=True), nargs=1)
def runSimulation(gui, no_warnings, step_len, pack_size, sim_time, on_collision, cfg_path, output_mode,outdir):
    # match output_mode with regex
    if _re.fullmatch(r'[exv]+', output_mode) is None:
        raise _click.BadParameter("Output mode must be a combination of [e]ncoded, [x]panded, [v]erbose (e.g., 'ex', 'v', 'exv').")

    controller = TraciController(
        gui=gui,
        cfg_path=cfg_path,
        step_len=step_len,
        frame_pack_size=pack_size,
        sim_time_s=sim_time,
        on_collision=CollisionAction(on_collision),
        warnings = not no_warnings
    )
    controller.run()
    _click.echo(f"{_Fore.GREEN}Simulation completed successfully.{_Style.RESET_ALL}")
    _click.echo(f"Total Packs Analyzed: {len(controller.plabels)}")
    _click.echo(f"Resulting Labels:")

    outdir = _Path(outdir) if outdir is not None else (_Path.cwd() / "plabels")
    if outdir.exists():
        _sh.rmtree(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    if 'e' in output_mode:
        controller.dumpEncoded(outdir / "plabels_encoded.csv")
        _click.echo(f"- Encoded labels dumped to {outdir / 'plabels_encoded.csv'}")
    if 'x' in output_mode:
        controller.dumpExpanded(outdir / "plabels_expanded.csv")
        _click.echo(f"- Expanded labels dumped to {outdir / 'plabels_expanded.csv'}")
    if 'v' in output_mode:
        controller.dumpVerbose(outdir / "plabels_verbose.csv")
        _click.echo(f"- Verbose labels dumped to {outdir / 'plabels_verbose.csv'}")


__all__ = ['runSimulation', 'TraciController', 'CollisionAction']