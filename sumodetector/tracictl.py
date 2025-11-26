import click as _click
from math import floor as _floor
import sumolib as _sumolib
import traci as _traci
from enum import Enum as _EN
from pathlib import Path as _Path
from .labels import LabelsEnum as _LE, MultiLabel as _MLB
from .map import MapParser as _MP, PedestrianAreaType as _PAT
from .sumocfg import SumoCfg as _SCFG
from .pack import PackData as _PKD, FrameData as _FD, VehicleData as _VD, VInfo as _VI, PInfo as _PI
from colorama import Fore as _Fore, Style as _Style
import re as _re
from shutil import rmtree as _rmrf
import time as _t
import numpy as _np
import pandas as _pd
from typing import Literal as _Lit
import tarfile as _tarfile
import multiprocessing as _mp
import sys as _sys
import signal as _signal
import os as _os
from time import perf_counter as _tpc

ACTIVE_LABELS = {
    _LE.LANE_CHANGE,
    _LE.LANE_MERGE,
    _LE.OVERTAKE,
    _LE.BRAKING,
    _LE.TURN_INTENT,
    _LE.COLLISION,
    _LE.PEDESTRIAN_IN_ROAD,
    _LE.OBSTACLE_IN_ROAD,
    _LE.TRAFFIC_JAM
}

def tlog(val:str):
    _click.echo(f"{_Fore.MAGENTA}[{_traci.simulation.getTime()}] {val}{_Style.RESET_ALL}")

class CollisionAction(_EN):
    TELEPORT = "teleport"
    WARN = "warn"
    NONE = "none"
    REMOVE = "remove"

def getStTypeFromVTypeID(vtype_id:str)->int:
    match = _re.search(r"^ST(\d+)(_|$)", vtype_id)
    if match:
        return int(match.group(1))
    else:
        raise ValueError(f"Invalid vType ID format: {vtype_id}")

def dumpParquet(dirpath:_Path, packs_df:_pd.DataFrame, labels_per_pid_df:_pd.DataFrame, vinfo_per_vid_df:_pd.DataFrame):
    tables = {
        "packs": packs_df,
        "labels": labels_per_pid_df,
        "vinfo": vinfo_per_vid_df,
    }
    for k,v in tables.items():
        fname = dirpath.resolve() / f"{k}.parquet"
        v.to_parquet(fname, index=False)

def loadParquet(dirpath:_Path)->tuple[_pd.DataFrame,_pd.DataFrame,_pd.DataFrame]:
    tables = []
    for k in ["packs", "labels", "vinfo"]:
        fname = dirpath.resolve() / f"{k}.parquet"
        tables.append( _pd.read_parquet(fname) )
    return tuple(tables)

def loadMergedParquet(dirpaths:list[_Path])->tuple[_pd.DataFrame,_pd.DataFrame,_pd.DataFrame]:
    packs = None
    labels = None
    vinfo = None
    first = True
    for dirpath in dirpaths:
        p, l, v = loadParquet(dirpath)
        packs = p if first else _pd.concat([packs, p], ignore_index=True)
        labels = l if first else _pd.concat([labels, l], ignore_index=True)
        vinfo = v if first else _pd.concat([vinfo, v], ignore_index=True)
        if first:
            first = False
    return packs, labels, vinfo

class TraciController:
    gui:bool
    step_len:float
    frame_pack_size:int
    start_time_s:float
    sim_time_s:float
    on_collision:CollisionAction
    warnings:bool
    emergency_insertions:bool
    sumobin:str
    delay:float
    total_steps:int
    total_packs:int

    max_speed_per_lane:dict[str,float]
    baseline_speed_per_lane:dict[str,float]
    slowdown_traffic_threshold:float
    traffic_jam_min_size:int
    braking_min_count:int

    vehs_lanes:dict[str,str]
    vehs_leaders:dict[str,str]
    vehs_lanes_no_junc_intlane:dict[str,float]

    map_parser:_MP
    cfg:_SCFG

    packs_df: _pd.DataFrame

    def __init__(self,*,gui:bool,sumo_cfg:_SCFG,step_len:float,frame_pack_size:int,sim_time_s:float,start_time_s:float,on_collision:CollisionAction,warnings:bool,emergency_insertions:bool,delay:float=None):
        self.gui = gui
        self.cfg = sumo_cfg
        self.step_len = step_len
        self.frame_pack_size = frame_pack_size
        self.start_time_s = start_time_s
        self.sim_time_s = sim_time_s
        self.on_collision = on_collision
        self.warnings = warnings
        self.emergency_insertions = emergency_insertions
        self.delay = delay

        self.sumobin = _sumolib.checkBinary('sumo-gui' if gui else 'sumo')
        self.total_steps = _floor(self.sim_time_s / self.step_len)
        self.total_packs = _floor(self.total_steps / self.frame_pack_size)

        self.map_parser = _MP(str(self.cfg.net_file))

        self.acc_braking_threshold = -2.0
        self.slowdown_traffic_threshold = 0.1
        self.merge_speed_threshold = 0.3
        self.traffic_jam_min_size = 8
        self.braking_min_count = 4

        # state
        self.vehs_lanes = dict()
        self.vehs_lanes_no_junc_intlane = dict()
        self.vehs_leaders = dict()
        self.packs_df = _pd.DataFrame()
        self.labels_per_pid_df = _pd.DataFrame()
        self.vinfo_per_vid_df = _pd.DataFrame()

    @staticmethod
    def __getVehEdge(vid:str)->str:
        if vid is None or vid not in _traci.vehicle.getIDList():
            return None
        lid = _traci.vehicle.getLaneID(vid)
        eid = _traci.lane.getEdgeID(lid)
        return eid

    @staticmethod
    def __getRealEdgeLeader(vid:str)->str:
        eid = TraciController.__getVehEdge(vid)
        vehs = sorted(filter( lambda x: not str(x).startswith("OBS_"), _traci.edge.getLastStepVehicleIDs(eid)),key=lambda x: _traci.vehicle.getLanePosition(x))

        nextv = None
        for i,vidi in enumerate(vehs):
            if vid == vidi:
                if i + 1 < len(vehs):
                    nextv = vehs[i + 1]
                break
        return nextv
    

    def __updateState(self):
        for vid in _traci.vehicle.getIDList():
            if not str(vid).startswith("OBS_"):
                lane_id = _traci.vehicle.getLaneID(vid) 
                leader_id = self.__getRealEdgeLeader(vid)
                self.vehs_leaders[vid] = leader_id
                self.vehs_lanes[vid] = lane_id
                if not self.map_parser.isLaneSpecial(lane_id):
                    self.vehs_lanes_no_junc_intlane[vid] = lane_id
    
    @staticmethod
    def __checkCollision(lb:_MLB)->bool:
        if lb.checkLabelDone(_LE.COLLISION):
            return True
        clist = _traci.simulation.getCollidingVehiclesIDList()
        if len(clist)>0:
            tlog(f"Collision detected among vehicles: {clist}")
            lb.setLabel(_LE.COLLISION)
            return True

    def __checkBraking(self,lb:_MLB)->bool:
        if lb.checkLabelDone(_LE.BRAKING):
            return True
        vbs = []
        for vid in _traci.vehicle.getIDList():
            if not str(vid).startswith("OBS_"):
                acc = _traci.vehicle.getAcceleration(vid)
                if acc < self.acc_braking_threshold:
                    vbs.append(vid)
                if len(vbs) >= self.braking_min_count:
                    tlog(f"Braking detected for vehicles: {vbs}")
                    lb.setLabel(_LE.BRAKING)
                    return True
            
    @staticmethod
    def __checkObstacles(lb:_MLB):
        if lb.checkLabelDone(_LE.OBSTACLE_IN_ROAD):
            return True
        for vid in _traci.vehicle.getIDList():
            if str(vid).startswith("OBS_"):
                tlog(f"Obstacle {vid} detected in simulation.")
                lb.setLabel(_LE.OBSTACLE_IN_ROAD)
                return 
            
    def __checkTrafficJam(self,lb:_MLB):
        if lb.checkLabelDone(_LE.TRAFFIC_JAM):
            return True
        for laneId in self.max_speed_per_lane.keys():

            vehs_in_lane:tuple[str] = _traci.lane.getLastStepVehicleIDs(laneId)
            if vehs_in_lane is None or len(vehs_in_lane) < self.traffic_jam_min_size:
                continue

            avg_speed = _np.mean([_traci.vehicle.getSpeed(vid) for vid in vehs_in_lane])

            ratio = avg_speed / self.baseline_speed_per_lane[laneId]
            if ratio < self.slowdown_traffic_threshold:
                tlog(f"Traffic jam detected on lane {laneId} with average speed {avg_speed:.2f} m/s ({ratio*100:.1f}% of baseline).")
                lb.setLabel(_LE.TRAFFIC_JAM)
                return
        

    def __checkLCLM(self,lb:_MLB):
        if lb.checkLabelDone(_LE.LANE_CHANGE) and lb.checkLabelDone(_LE.LANE_MERGE):
            return True
        for vid in _traci.vehicle.getIDList():
            if not str(vid).startswith("OBS_"):
                lane_id = _traci.vehicle.getLaneID(vid)
                prev_lane_id = self.vehs_lanes.get(vid,None)
                if prev_lane_id is not None and lane_id != prev_lane_id:
                    e1id = _traci.lane.getEdgeID(prev_lane_id)
                    e2id = _traci.lane.getEdgeID(lane_id)
                    if e1id == e2id:
                        # generic lc situation
                        if not lb.checkLabelDone(_LE.LANE_CHANGE):
                            lb.setLabel(_LE.LANE_CHANGE)
                            tlog(f"Vehicle {vid} changed lane from {prev_lane_id} to {lane_id} on edge {e1id}.")
                        if not lb.checkLabelDone(_LE.LANE_MERGE):
                            is_lc_lm = self.map_parser.checkIfLcLm(prev_lane_id,lane_id)
                            if is_lc_lm:
                                lb.setLabel(_LE.LANE_MERGE)
                                tlog(f"Vehicle {vid} performed Lane Change corresponding to Lane Merge from lane {prev_lane_id} to {lane_id} on edge {e1id}.")
                        return True
                    
    def __checkOvertake(self,lb:_MLB):
        if lb.checkLabelDone(_LE.OVERTAKE):
            return True
        for vid in _traci.vehicle.getIDList():
            if not str(vid).startswith("OBS_"):
                old_leader_id = self.vehs_leaders.get(vid,None)
                current_leader_id = self.__getRealEdgeLeader(vid)
                if old_leader_id is not None and current_leader_id != old_leader_id and (self.__getVehEdge(vid) == self.__getVehEdge(old_leader_id)):
                    lb.setLabel(_LE.OVERTAKE)
                    tlog(f"Detected Overtake of Vehicle {vid} on {old_leader_id}")
                    return True
                        
    def __checkTurn(self,lb:_MLB):
        if lb.checkLabelDone(_LE.TURN_INTENT):
            return True
        for vid in _traci.vehicle.getIDList():
            if not str(vid).startswith("OBS_"):
                lane_id = _traci.vehicle.getLaneID(vid)
                prev_lane_id = self.vehs_lanes_no_junc_intlane.get(vid,None)
                if prev_lane_id is not None and lane_id is not None and lane_id != prev_lane_id and (not self.map_parser.isLaneSpecial(lane_id)):
                    cont_lane_id = self.map_parser.getContToLaneId(from_lane_id=prev_lane_id)
                    if cont_lane_id is None or lane_id != cont_lane_id:
                        # turning detected
                        lb.setLabel(_LE.TURN_INTENT)
                        tlog(f"Vehicle {vid} performed turn from lane {prev_lane_id} to {lane_id}.")
                        return True
                   
    def __checkPedestrianInRoad(self,lb:_MLB):
        if lb.checkLabelDone(_LE.PEDESTRIAN_IN_ROAD):
            return True
        for pid in _traci.person.getIDList():
            laneid=_traci.person.getLaneID(pid)
            is_pedestrian_area, area_type = self.map_parser.isPedestrianArea(laneid)
            if not is_pedestrian_area:
                lb.setLabel(_LE.PEDESTRIAN_IN_ROAD)
                tlog(f"Detected Pedestrian {pid} in road lane {laneid}")
                return True
            elif area_type==_PAT.CROSSING_TLS:
                # if crossing with tls, further check if it has right of way
                links = _traci.lane.getLinks(laneid, extended=True)
                for (succLane, hasPrio, isOpen, hasFoe, *_) in links:
                    # isOpen=True => semaforo verde o priorità libera
                    # hasFoe=False => nessuna lane conflittuale con precedenza
                    if (not isOpen) or hasFoe:
                        lb.setLabel(_LE.PEDESTRIAN_IN_ROAD)
                        tlog(f"Detected Pedestrian {pid} in crossing with traffic light lane {laneid} without right of way")
                        return True
                    
                        
    def __checkFrame(self,lb:_MLB):
        self.__checkLCLM(lb)
        self.__checkOvertake(lb)
        self.__checkBraking(lb)
        self.__checkTurn(lb)
        self.__checkCollision(lb)
        self.__checkPedestrianInRoad(lb)
        self.__checkObstacles(lb)
        self.__checkTrafficJam(lb)

    
    def tryAddVInfo(self,vid:str,*,w:float=None,l:float=None,stType:int,pedestrian:bool=False):
        if "VehicleId" in self.vinfo_per_vid_df.columns and not self.vinfo_per_vid_df["VehicleId"].empty and vid in self.vinfo_per_vid_df["VehicleId"].values:
            return False
        else:
            if pedestrian:
                if w is not None or l is not None:
                    raise ValueError("Pedestrian VInfo cannot have width or length.")
                df = _PI(id=vid,stType=stType).asPandas()
            else:
                if w is None or l is None:
                    raise ValueError("Vehicle VInfo must have width and length.")
                df = _VI(id=vid,stType=stType,width=w,length=l).asPandas()
            self.vinfo_per_vid_df = _pd.concat([self.vinfo_per_vid_df, df], ignore_index=True)
            return True
            
                        
    
    def computeFrameData(self,*,id:int) -> _FD:
        frame = _FD(id=id)
        for pid in _traci.person.getIDList():
            pos = _traci.person.getPosition(pid)
            speed = _traci.person.getSpeed(pid)
            angle = _traci.person.getAngle(pid)
            vtid = _traci.person.getTypeID(pid)
            self.tryAddVInfo(pid,stType=getStTypeFromVTypeID(vtid),pedestrian=True)
            pdata = _VD(id=pid, position=pos, speed=speed, angle=angle)
            frame.pedestrians.append(pdata)
        for vid in _traci.vehicle.getIDList():
            if not str(vid).startswith("OBS_"):
                pos = _traci.vehicle.getPosition(vid)
                speed = _traci.vehicle.getSpeed(vid)
                angle = _traci.vehicle.getAngle(vid)
                vtid = _traci.vehicle.getTypeID(vid)
                width = _traci.vehicle.getWidth(vid)
                length = _traci.vehicle.getLength(vid)
                self.tryAddVInfo(vid,w=width,l=length,stType=getStTypeFromVTypeID(vtid))
                vdata = _VD(id=vid, position=pos, speed=speed, angle=angle)
                frame.vehicles.append(vdata)
        return frame
    
    def run(self):
        args = [
            self.sumobin,
            "-c", str(self.cfg.sumocfg_file),
            "--collision.action", self.on_collision.value,
            "--collision.check-junctions", "true",
            "--time-to-teleport", "0",
            "--lanechange.duration", "3.5",
            "--time-to-impatience", "40",
            "--no-step-log",
        ]
        args.extend(["--no-warnings", "false" if self.warnings else "true"])
        #args.extend(["--lateral-resolution", "0.1" ])

        if self.emergency_insertions:
            args.extend(["--emergency-insert", "true"])
        args.append('--start')
        _click.echo(f"{_Fore.WHITE}{_Style.DIM}Starting SUMO (with command: {' '.join(args)}){_Style.RESET_ALL}")
        _traci.start(args)
        laneIds = _traci.lane.getIDList()
        self.max_speed_per_lane = {lid: _traci.lane.getMaxSpeed(lid) for lid in laneIds}
        self.baseline_speed_per_lane = self.max_speed_per_lane.copy()
        lb = _MLB(active_labels=ACTIVE_LABELS)

        if self.start_time_s > 0.0:
            tlog(f"Skipping to start time {self.start_time_s}s...")
            _traci.simulationStep(self.start_time_s-self.step_len)
            self.__updateState()
            _traci.simulationStep()

        for pn in range(self.total_packs):
            lb.clear()
            pack = _PKD(id=pn)

            for fn in range(self.frame_pack_size):
                _traci.simulationStep()

                self.__checkFrame(lb)

                frame_data = self.computeFrameData(id=fn)
                pack.frames.append(frame_data)

                # end of frame analysis: update and wait for next
                self.__updateState()
                if self.delay is not None:
                    _t.sleep(self.delay)

            self.packs_df = _pd.concat([self.packs_df, pack.asPandas()], ignore_index=True)
            self.labels_per_pid_df = _pd.concat([self.labels_per_pid_df, lb.asPandas(pn)], ignore_index=True)
        
        tend = _traci.simulation.getTime()
        tlog(f"Simulation ended at time {tend}, closing SUMO...", enabled=True)
        _traci.close() 

    def dumpParquet(self,dirpath:_Path):
        dumpParquet(dirpath, self.packs_df, self.labels_per_pid_df, self.vinfo_per_vid_df)

def tar(src_folder:_Path):
    if not src_folder.is_dir():
        raise ValueError(f"Source folder '{src_folder}' is not a directory")
    tarpath = src_folder.with_suffix('.tar')
    with _tarfile.open(tarpath, "w") as tar:
        tar.add(src_folder, arcname="data")

def tctl_worker(gui,scfg,step_len,frame_pack_size,start_time_s,sim_time_s,on_collision,warnings,emergency_insertions,delay,*,queue:_mp.Queue, idx:int, excqueue:_mp.Queue, temp_path:_Path=None):
    bp = temp_path if temp_path is not None else _Path.cwd()
    controller = TraciController(
        gui=gui,
        sumo_cfg=scfg,
        step_len=step_len,
        frame_pack_size=frame_pack_size,
        start_time_s=start_time_s,
        sim_time_s=sim_time_s,
        on_collision=on_collision,
        warnings=warnings,
        emergency_insertions=emergency_insertions,
        delay=delay
    )
    def handle_sigusr1(signum, frame):
        _click.echo(f"{_Fore.YELLOW}Worker {idx} received SIGUSR1 ({signum}), terminating simulation...{_Style.RESET_ALL}")
        if _traci.isLoaded():
            _traci.close()
        _sys.exit(0)
    _signal.signal(_signal.SIGUSR1, handle_sigusr1)
    try:
        controller.run()
        tempdir = bp / f"w{idx:02d}"
        tempdir.mkdir(parents=True, exist_ok=True)
        controller.dumpParquet(tempdir)
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

@_click.command()
@_click.option('--gui','-g', is_flag=True, default=False, help='Run SUMO with GUI')
@_click.option('--no-warnings', is_flag=True, default=False, help='Suppress SUMO warnings.')
@_click.option('--no-emergency-insertions', is_flag=True, default=False, help='Disable insertion of emergency vehicles during simulation (default: False).')
@_click.option('--step-len','-s', type=float, default=0.2, help='Length of each simulation step in seconds (default: 0.2s).')
@_click.option('--pack-size','-p', type=int, default=20, help='Number of frames in each pack (default: 20).')
@_click.option('--sim-time','-t', type=float, default=500.0, help='Total simulation time in seconds (default: 500s).')
@_click.option('--on-collision', type=_click.Choice([e.value for e in CollisionAction]), default=CollisionAction.TELEPORT.value, help='Action to take on collision (default: remove).')
@_click.option('--outdir', type=_click.Path(file_okay=False, dir_okay=True, writable=True), required=True, help='Output directory for label files (required).')
@_click.option('--delay', '-d', type=float, default=None, help='Delay in ms between simulation steps (default: no delay).')
@_click.option('--tar','tar_opt', is_flag=True, default=False, help='Create a tar archive of the output directory after simulation. No need for .gz compression since files are parquet format.')
@_click.option('-M', '--multi-threaded', 'multi_threaded', is_flag=True, default=False, help='Whether to run the simulation in multi-threaded mode (default: False).')
@_click.argument('cfg_path', type=_click.Path(exists=True), nargs=1)
def runSimulation(gui, no_warnings, no_emergency_insertions, step_len, pack_size, sim_time, on_collision, cfg_path,outdir, delay, tar_opt, multi_threaded):
    
    sumo_cfg = _SCFG(_Path(cfg_path))

    if sumo_cfg.step_length_s is not None:
        step_len = sumo_cfg.step_length_s
    if sumo_cfg.duration_s is not None:
        sim_time = sumo_cfg.duration_s

    outdir = _Path(outdir)
    if outdir.exists():
        _rmrf(outdir)
    if outdir.with_suffix('.tar').exists():
        outdir.with_suffix('.tar').unlink()
    outdir.mkdir(parents=True, exist_ok=True)

    controller: TraciController = None

    start_time = _tpc()

    if multi_threaded:
        nprocs = _mp.cpu_count() // 2
        # use half of available CPUs to avoid overloading
        _click.echo(f"{_Fore.GREEN}Running simulation in multi-threaded mode with {nprocs} workers...{_Style.RESET_ALL}")
        queue = _mp.Queue()
        excqueue = _mp.Queue()
        processes: list[_mp.Process] = []

        sim_time_per_cpu = sim_time / nprocs
        workers_cache_path = (sumo_cfg.sumocfg_file.parent / '.workers_tmp').resolve()
        if workers_cache_path.exists():
            _rmrf(workers_cache_path)

        for i in range(nprocs):
            p = _mp.Process(target=tctl_worker, args=(
                gui,
                sumo_cfg,
                step_len,
                pack_size,
                i * sim_time_per_cpu,
                sim_time_per_cpu,
                CollisionAction(on_collision),
                not no_warnings,
                not no_emergency_insertions,
                delay,
            ), kwargs={'queue': queue, 'idx': i, 'excqueue': excqueue, 'temp_path': workers_cache_path})
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
        else:
            _sys.exit(-1)
            
        fnames = []
        for i in range(nprocs):
            print(f"{_Fore.GREEN}Collected results from worker #{i}{_Style.RESET_ALL}")
            fnames.append( queue.get() )
        # sort controllers by idx
        fnames.sort(key=lambda x: x[0])
        fnames = [f[1] for f in fnames]
        fdata = loadMergedParquet(fnames)
        dumpParquet(outdir, *fdata)
        _rmrf(workers_cache_path)


    else:
        _click.echo(f"{_Fore.GREEN}Running simulation in single-threaded mode...{_Style.RESET_ALL}")
        controller = TraciController(
            gui=gui,
            sumo_cfg=sumo_cfg,
            step_len=step_len,
            frame_pack_size=pack_size,
            start_time_s=0.0,
            sim_time_s=sim_time,
            on_collision=CollisionAction(on_collision),
            warnings=not no_warnings,
            emergency_insertions=not no_emergency_insertions,
            delay=delay
        )
        controller.run()
        controller.dumpParquet(outdir)
    
    end_time = _tpc()
    elapsed = end_time - start_time
    _click.echo(f"{_Fore.GREEN}Simulation completed successfully in {elapsed:.2f} seconds.{_Style.RESET_ALL}")
    _click.echo(f"- All data dumped in parquet format to {outdir}")

    if tar_opt:
        tar(outdir.resolve())
        _click.echo(f"- Output directory archived to {outdir.with_suffix('.tar')}")
        _rmrf(outdir.resolve())

        

__all__ = ['runSimulation', 'TraciController', 'CollisionAction']