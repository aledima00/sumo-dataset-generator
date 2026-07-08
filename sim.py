import click
from pathlib import Path
from typing import get_args

from sumodetector.console import SimulationController as SimCtl
from sumodetector.labels import LabelsEnum as _LE
from sumodetector.tracictl import CollisionAction
from sumodetector.packBufferedWriter import OpMode
        


@click.command()
@click.option('-L', '--label', 'label', type=int, required=True, help='Label to extract. 0 for LANE_CHANGE, 1 for OVERTAKE, 2 for TURN, 3 for COLLISION.')
@click.option('--gui','-g', is_flag=True, default=False, help='Run SUMO with GUI')
@click.option('-W','--no-warnings', is_flag=True, default=False, help='Suppress SUMO warnings.')
@click.option('-E','--enable-emergency-insertions', 'enable_emergency_insertions', is_flag=True, default=False, help='Enable insertion of emergency vehicles during simulation (default: False).')
@click.option('--pack-size','-p', type=int, default=20, help='Number of frames in each pack (default: 20).')
@click.option('--on-collision', type=click.Choice(get_args(CollisionAction)), default=None, help='Action to take on collision (default: None).')
@click.option('--outdir', type=click.Path(file_okay=False, dir_okay=True, writable=True, path_type=Path), required=True, help='Output directory for label files (required).')
@click.option('--delay', '-d', type=float, default=None, help='Delay in ms between simulation steps (default: no delay).')
@click.option('--tar','tar_opt', is_flag=True, default=False, help='Create a tar archive of the output directory after simulation. No need for .gz compression since files are parquet format.')
@click.option('-T', '--threads', 'threads', type=int, default=1, help='Number of threads to use for multi-threaded simulation (default: 1).')
@click.option('--map-only', is_flag=True, default=False, help='Only extract the vector map without running the full simulation (default: False).')
@click.option('-S', '--split', is_flag=True, default=False, help='Whether to split the simulation into multiple parts (default: False). Only used in multi-threaded mode.')
@click.option('-O', '--opmode', 'opmode', type=click.Choice(get_args(OpMode)), default='absolute', help='Operation mode for PackBufferedWriter (default: absolute).')
@click.argument('basepath', type=click.Path(exists=True, dir_okay=True, file_okay=True, path_type=Path), nargs=1)
def console(label:int, gui:bool, no_warnings:bool, enable_emergency_insertions:bool, pack_size:int, on_collision:CollisionAction, basepath:Path,outdir:Path, delay:float, tar_opt:bool, threads:int, map_only:bool, split:bool, opmode:OpMode):
    if gui and threads > 1:
        raise click.UsageError("--gui can only be used in single-threaded mode (threads=1).")

    if split and threads <= 1:
        raise click.UsageError("--split requires threads > 1.")

    simctl = SimCtl(
        active_labels={label},
        gui=gui,
        no_warnings=no_warnings,
        enable_emergency_insertions=enable_emergency_insertions,
        pack_size=pack_size,
        on_collision=on_collision,
        basepath=basepath,
        outdir=outdir,
        delay=delay,
        tar_opt=tar_opt,
        threads=threads,
        map_only=map_only,
        split=split,
        pbw_opmode=opmode
    )
    simctl.run()

if __name__ == "__main__":
    console()