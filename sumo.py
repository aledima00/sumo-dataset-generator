import click
from pathlib import Path
from typing import get_args

from sumodetector.console import SimulationController as SimCtl
from sumodetector.labels import LabelsEnum as _LE
from sumodetector.tracictl import CollisionAction
from sumodetector.packBufferedWriter import OpMode
        

ACTIVE_LABELS = {_LE.COLLISION}

@click.command()
@click.option('--gui','-g', is_flag=True, default=False, help='Run SUMO with GUI')
@click.option('-W','--no-warnings', is_flag=True, default=False, help='Suppress SUMO warnings.')
@click.option('-E','--enable-emergency-insertions', 'enable_emergency_insertions', is_flag=True, default=False, help='Enable insertion of emergency vehicles during simulation (default: False).')
@click.option('--pack-size','-p', type=int, default=20, help='Number of frames in each pack (default: 20).')
@click.option('--on-collision', type=click.Choice(get_args(CollisionAction)), default=None, help='Action to take on collision (default: None).')
@click.option('--outdir', type=click.Path(file_okay=False, dir_okay=True, writable=True, path_type=Path), required=True, help='Output directory for label files (required).')
@click.option('--delay', '-d', type=float, default=None, help='Delay in ms between simulation steps (default: no delay).')
@click.option('--tar','tar_opt', is_flag=True, default=False, help='Create a tar archive of the output directory after simulation. No need for .gz compression since files are parquet format.')
@click.option('-M', '--multi-threaded', 'multi_threaded', is_flag=True, default=False, help='Whether to run the simulation in multi-threaded mode (default: False).')
@click.option('--map-only', is_flag=True, default=False, help='Only extract the vector map without running the full simulation (default: False).')
@click.option('-S', '--split', is_flag=True, default=False, help='Whether to split the simulation into multiple parts (default: False). Only used in multi-threaded mode.')
@click.option('-O', '--opmode', 'opmode', type=click.Choice(get_args(OpMode)), default='absolute', help='Operation mode for PackBufferedWriter (default: absolute).')
@click.argument('basepath', type=click.Path(exists=True, dir_okay=True, file_okay=True, path_type=Path), nargs=1)
def console(gui:bool, no_warnings:bool, enable_emergency_insertions:bool, pack_size:int, on_collision:CollisionAction, basepath:Path,outdir:Path, delay:float, tar_opt:bool, multi_threaded:bool, map_only:bool, split:bool, tup:tup_type, opmode:OpMode):
    simctl = SimCtl(
        active_labels=ACTIVE_LABELS,
        gui=gui,
        no_warnings=no_warnings,
        enable_emergency_insertions=enable_emergency_insertions,
        pack_size=pack_size,
        on_collision=on_collision,
        basepath=basepath,
        outdir=outdir,
        delay=delay,
        tar_opt=tar_opt,
        multi_threaded=multi_threaded,
        map_only=map_only,
        split=split,
        pbw_opmode=opmode
    )
    simctl.run()

if __name__ == "__main__":
    console()