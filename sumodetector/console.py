from pathlib import Path as _Path
from tqdm.auto import tqdm as _tqdm
import sys as _sys
import signal as _signal
import os as _os
from time import perf_counter as _tpc
import tarfile as _tarfile
import multiprocessing as _mp
import click as _click
import traci as _traci
from shutil import rmtree as _rmrf
from colorama import Fore as _Fore, Style as _Style
from typing import get_args
import pandas as _pd
import pyarrow as _pa
import pyarrow.parquet as _pq
from math import floor as _floor

from .pack import PackSchema as _PKS
from .tracictl import TraciController, CollisionAction
from .sumocfg import SumoCfg as _SCFG
from .labels import LabelsEnum as _LE

ACTIVE_LABELS = {
    _LE.LANE_CHANGE
}


def getMaxPackId(df:_pd.DataFrame)->int:
    """
    Get the maximum PackId from a packs DataFrame.
    """
    if df.empty:
        return None
    return df['PackId'].max()

def concatWithOffset(df1:_pd.DataFrame, df2:_pd.DataFrame, offset:int)->_pd.DataFrame:
    """
    Concatenate two packs DataFrames, adjusting the 'PackId' in df2 to avoid overlaps.
    """
    if df1.empty:
        return df2.copy()
    if df2.empty:
        return df1.copy()
    df2_adjusted = df2.copy()
    if offset is not None:
        df2_adjusted['PackId'] += offset
    return _pd.concat([df1, df2_adjusted], ignore_index=True)

def concatNoDuplicates(df1:_pd.DataFrame, df2:_pd.DataFrame, keycol:str)->_pd.DataFrame:
    """
    Concatenate two DataFrames, avoiding duplicates based on a key column.
    """
    if df1.empty:
        return df2.copy()
    if df2.empty:
        return df1.copy()
    existing_keys = set(df1[keycol].unique())
    df2_filtered = df2[~df2[keycol].isin(existing_keys)]
    return _pd.concat([df1, df2_filtered], ignore_index=True)

def mergeDirs(dirpaths:list[_Path], outdir:_Path):
    lb_df = None
    vi_df = None
    pkwriter = _pq.ParquetWriter(str(outdir / "packs.parquet"), _PKS())
    for dirpath in dirpaths:
        cur_lb_df = _pd.read_parquet(dirpath / "labels.parquet")
        cur_vi_df = _pd.read_parquet(dirpath / "vinfo.parquet")

        pid_offset = 0 if lb_df is None else getMaxPackId(lb_df) + 1
        lb_df = cur_lb_df if lb_df is None else concatWithOffset(lb_df, cur_lb_df, pid_offset)
        vi_df = cur_vi_df if vi_df is None else concatNoDuplicates(vi_df, cur_vi_df, keycol="VehicleId")

        # stream packs from one dir to output, also here applying PackId offset
        pkreader = _pq.ParquetFile(str(dirpath / "packs.parquet"))
        ngroups = pkreader.num_row_groups
        for i in range(ngroups):
            t1 = pkreader.read_row_group(i)
            df = t1.to_pandas()
            df['PackId'] += pid_offset
            t2 = _pa.Table.from_pandas(df)
            pkwriter.write_table(t2)
        # close reader
        pkreader.close()

        # delete dirpath
        _rmrf(dirpath)

    lb_df.to_parquet(outdir / "labels.parquet", index=False)
    vi_df.to_parquet(outdir / "vinfo.parquet", index=False)
    pkwriter.close()


def tar(src_folder:_Path):
    if not src_folder.is_dir():
        raise ValueError(f"Source folder '{src_folder}' is not a directory")
    tarpath = src_folder.with_suffix('.tar')
    with _tarfile.open(tarpath, "w") as tar:
        tar.add(src_folder, arcname="data")

def tctl_worker(gui,scfg,frame_pack_size,start_time_s,sim_time_s,on_collision,warnings,emergency_insertions,delay,*,queue:_mp.Queue,progress_queue:_mp.Queue, idx:int, excqueue:_mp.Queue, temp_path:_Path=None):
    # CONTROL THIS IMPLEMENTATION
    bp = temp_path if temp_path is not None else _Path.cwd()
    controller = TraciController(
        gui=gui,
        sumo_cfg=scfg,
        frame_pack_size=frame_pack_size,
        start_time_s=start_time_s,
        sim_time_s=sim_time_s,
        on_collision=on_collision,
        warnings=warnings,
        emergency_insertions=emergency_insertions,
        delay=delay,
        printfunc=_click.echo,
        tlog=False,
        active_labels=ACTIVE_LABELS
    )
    def handle_sigusr1(signum, frame):
        _click.echo(f"{_Fore.YELLOW}Worker {idx} received SIGUSR1 ({signum}), terminating simulation...{_Style.RESET_ALL}")
        if _traci.isLoaded():
            _traci.close()
        _sys.exit(0)
    _signal.signal(_signal.SIGUSR1, handle_sigusr1)
    try:
        tempdir = bp / f"w{idx:02d}"
        if tempdir.exists():
            _rmrf(tempdir)
        tempdir.mkdir(parents=True, exist_ok=True)
        controller.run(save_dirpath=tempdir,progress_queue=progress_queue)
        queue.put( (idx, tempdir) )
    except KeyboardInterrupt as kbdint:
        _click.echo(f"{_Fore.RED}Worker {idx} interrupted by KeyboardInterrupt, terminating...{_Style.RESET_ALL}")
        if _traci.isLoaded():
            _traci.close()
        excqueue.put((idx, kbdint))
        _sys.exit(1)
    except Exception as e:
        _click.echo(f"{_Fore.RED}Worker {idx} encountered an error: {e}{_Style.RESET_ALL}")
        if _traci.isLoaded():
            _traci.close()
        excqueue.put((idx, e))
        _sys.exit(2)

def ctlworker(worker_processes:list[_mp.Process],excqueue:_mp.Queue):
    excfound = False
    while not excfound:
        try:
            exc = excqueue.get(timeout=1)
            excfound = True
            for i,p in enumerate(worker_processes):
                if p.is_alive() and i != exc[0]:
                    _os.kill(p.pid, _signal.SIGUSR1)
        except Exception:
            # timeout -> no exception found in 1s
            pass

def tqdm_logger_worker(totFrames:int, doneQueue:_mp.Queue):
    progress=_tqdm(total=totFrames, desc="Simulation Progress", unit="frames")
    done = 0
    while done < totFrames:
        val = doneQueue.get()
        done += val
        progress.update(val)
    progress.close()

@_click.command()
@_click.option('--gui','-g', is_flag=True, default=False, help='Run SUMO with GUI')
@_click.option('--no-warnings', is_flag=True, default=False, help='Suppress SUMO warnings.')
@_click.option('-E','--enable-emergency-insertions', 'enable_emergency_insertions', is_flag=True, default=False, help='Enable insertion of emergency vehicles during simulation (default: False).')
@_click.option('--pack-size','-p', type=int, default=20, help='Number of frames in each pack (default: 20).')
@_click.option('--on-collision', type=_click.Choice(get_args(CollisionAction)), default=None, help='Action to take on collision (default: None).')
@_click.option('--outdir', type=_click.Path(file_okay=False, dir_okay=True, writable=True), required=True, help='Output directory for label files (required).')
@_click.option('--delay', '-d', type=float, default=None, help='Delay in ms between simulation steps (default: no delay).')
@_click.option('--tar','tar_opt', is_flag=True, default=False, help='Create a tar archive of the output directory after simulation. No need for .gz compression since files are parquet format.')
@_click.option('-M', '--multi-threaded', 'multi_threaded', is_flag=True, default=False, help='Whether to run the simulation in multi-threaded mode (default: False).')
@_click.argument('cfg_path', type=_click.Path(exists=True), nargs=1)
def runSimulation(gui, no_warnings, enable_emergency_insertions, pack_size, on_collision, cfg_path,outdir, delay, tar_opt, multi_threaded):
    
    sumo_cfg = _SCFG(_Path(cfg_path))
    sumo_cfg.checkReqParams()

    outdir = _Path(outdir)
    if outdir.exists():
        _rmrf(outdir)
    if outdir.with_suffix('.tar').exists():
        outdir.with_suffix('.tar').unlink()
    outdir.mkdir(parents=True, exist_ok=True)

    start_time = _tpc()

    nprocs = _mp.cpu_count() // 2 if multi_threaded else 1
    # use half of available CPUs to avoid overloading
    _click.echo(f"{_Fore.GREEN}Running simulation with {nprocs} worker{'s in parallel' if nprocs > 1 else ''}...{_Style.RESET_ALL}")
    queue = _mp.Queue()
    excqueue = _mp.Queue()
    progress_queue = _mp.Queue()
    processes: list[_mp.Process] = []

    sim_time_per_cpu = sumo_cfg.duration_s / nprocs
    workers_cache_path = (sumo_cfg.sumocfg_file.parent / '.workers_tmp').resolve()
    if workers_cache_path.exists():
        _rmrf(workers_cache_path)

    # progress logger
    tot_frames = (_floor(sim_time_per_cpu / sumo_cfg.step_length_s)) * nprocs
    progress_logger_proc = _mp.Process(target=tqdm_logger_worker, args=(tot_frames, progress_queue))
    progress_logger_proc.start()

    for i in range(nprocs):
        p = _mp.Process(target=tctl_worker, args=(
            gui,
            sumo_cfg,
            pack_size,
            i * sim_time_per_cpu,
            sim_time_per_cpu,
            on_collision,
            not no_warnings,
            enable_emergency_insertions,
            delay,
        ), kwargs={'queue': queue, 'progress_queue': progress_queue, 'idx': i, 'excqueue': excqueue, 'temp_path': workers_cache_path})
        processes.append(p)
        p.start()

    ctl_proc = _mp.Process(target=ctlworker, args=(processes, excqueue))
    ctl_proc.start()

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt as kbdint:
        # keyboard interrupt in main thread
        _click.echo(f"{_Fore.RED}KeyboardInterrupt received, terminating all processes...{_Style.RESET_ALL}")
        excqueue.put( (-1, kbdint) )
    except Exception as e:
        # exception in main thread
        _click.echo(f"{_Fore.RED}An error occurred during multi-threaded simulation: {e}{_Style.RESET_ALL}")
        excqueue.put( (-1, e) )

    if ctl_proc.is_alive():
        ctl_proc.terminate()
        ctl_proc.join()
    else:
        _sys.exit(-1)

    if progress_logger_proc.is_alive():
        progress_logger_proc.terminate()
    progress_logger_proc.join()
        
    dirnames = []
    for i in range(nprocs):
        print(f"{_Fore.GREEN}Collected results from worker #{i}{_Style.RESET_ALL}")
        dirnames.append( queue.get() )
    # sort controllers by idx
    dirnames.sort(key=lambda x: x[0])
    dirnames = [f[1] for f in dirnames]
    mergeDirs(dirnames, outdir)
    _rmrf(workers_cache_path)
    
    end_time = _tpc()
    elapsed = end_time - start_time
    _click.echo(f"{_Fore.GREEN}Simulation completed successfully in {elapsed:.2f} seconds.{_Style.RESET_ALL}")
    _click.echo(f"- All data dumped in parquet format to {outdir}")

    if tar_opt:
        tar(outdir.resolve())
        _click.echo(f"- Output directory archived to {outdir.with_suffix('.tar')}")
        _rmrf(outdir.resolve())