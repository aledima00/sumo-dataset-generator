import click as _click
from math import floor as _floor
import sumolib as _sumolib
import traci as _traci
from enum import Enum as _EN
from pathlib import Path as _Path
from .labels import LabelsEnum as _LE, MultiLabel as _MLB
from .map import MapParser as _MP, PedestrianAreaType as _PAT
from .sumocfg import SumoCfg as _SCFG
from .pack import PackData as _PKD, FrameData as _FD, VehicleData as _VD
from colorama import Fore as _Fore, Style as _Style
import re as _re
import shutil as _sh
import time as _t
import numpy as _np
import pandas as _pd
from typing import Literal as _Lit

def tlog(val:str):
    _click.echo(f"{_Fore.MAGENTA}[{_traci.simulation.getTime()}] {val}{_Style.RESET_ALL}")

class CollisionAction(_EN):
    TELEPORT = "teleport"
    WARN = "warn"
    NONE = "none"
    REMOVE = "remove"


class TraciController:
    plabels:list[_MLB]
    gui:bool
    step_len:float
    frame_pack_size:int
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

    def __init__(self,*,gui:bool,sumo_cfg:_SCFG,step_len:float,frame_pack_size:int,sim_time_s:float,on_collision:CollisionAction,warnings:bool,emergency_insertions:bool,delay:float=None):
        self.plabels = []
        self.gui = gui
        self.cfg = sumo_cfg
        self.step_len = step_len
        self.frame_pack_size = frame_pack_size
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
    def __checkCollision(lb)->bool:
        if lb.checkLabel(_LE.COLLISION):
            return True
        clist = _traci.simulation.getCollidingVehiclesIDList()
        if len(clist)>0:
            tlog(f"Collision detected among vehicles: {clist}")
            lb.setLabel(_LE.COLLISION)
            return True

    def __checkBraking(self,lb)->bool:
        if lb.checkLabel(_LE.BRAKING):
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
    def __checkObstacles(lb):
        if lb.checkLabel(_LE.OBSTACLE_IN_ROAD):
            return True
        for vid in _traci.vehicle.getIDList():
            if str(vid).startswith("OBS_"):
                tlog(f"Obstacle {vid} detected in simulation.")
                lb.setLabel(_LE.OBSTACLE_IN_ROAD)
                return 
            
    def __checkTrafficJam(self,lb):
        if lb.checkLabel(_LE.TRAFFIC_JAM):
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
        if lb.checkLabel(_LE.LANE_CHANGE) and lb.checkLabel(_LE.LANE_MERGE):
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
                        if not lb.checkLabel(_LE.LANE_CHANGE):
                            lb.setLabel(_LE.LANE_CHANGE)
                            tlog(f"Vehicle {vid} changed lane from {prev_lane_id} to {lane_id} on edge {e1id}.")
                        if not lb.checkLabel(_LE.LANE_MERGE):
                            is_lc_lm = self.map_parser.checkIfLcLm(prev_lane_id,lane_id)
                            if is_lc_lm:
                                lb.setLabel(_LE.LANE_MERGE)
                                tlog(f"Vehicle {vid} performed Lane Change corresponding to Lane Merge from lane {prev_lane_id} to {lane_id} on edge {e1id}.")
                        return True
                    
    def __checkOvertake(self,lb):
        if lb.checkLabel(_LE.OVERTAKE):
            return True
        for vid in _traci.vehicle.getIDList():
            if not str(vid).startswith("OBS_"):
                old_leader_id = self.vehs_leaders.get(vid,None)
                current_leader_id = self.__getRealEdgeLeader(vid)
                if old_leader_id is not None and current_leader_id != old_leader_id and (self.__getVehEdge(vid) == self.__getVehEdge(old_leader_id)):
                    lb.setLabel(_LE.OVERTAKE)
                    tlog(f"Detected Overtake of Vehicle {vid} on {old_leader_id}")
                    return True
                        
    def __checkTurn(self,lb):
        if lb.checkLabel(_LE.TURN_INTENT):
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
                   
    def __checkPedestrianInRoad(self,lb):
        if lb.checkLabel(_LE.PEDESTRIAN_IN_ROAD):
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
                    
                        
    def __checkFrame(self,lb):
        self.__checkCollision(lb)
        self.__checkBraking(lb)
        self.__checkObstacles(lb)
        self.__checkTrafficJam(lb)
        self.__checkLCLM(lb)
        self.__checkOvertake(lb)
        self.__checkTurn(lb)
        self.__checkPedestrianInRoad(lb)
                        
    
    @staticmethod
    def computeFrameData(*,id:int) -> _FD:
        frame = _FD(id=id)
        for pid in _traci.person.getIDList():
            pos = _traci.person.getPosition(pid)
            speed = _traci.person.getSpeed(pid)
            angle = _traci.person.getAngle(pid)
            pdata = _VD(id=pid, position=pos, speed=speed, angle=angle, type="pedestrian")
            frame.pedestrians.append(pdata)
        for vid in _traci.vehicle.getIDList():
            if not str(vid).startswith("OBS_"):
                pos = _traci.vehicle.getPosition(vid)
                speed = _traci.vehicle.getSpeed(vid)
                angle = _traci.vehicle.getAngle(vid)
                vdata = _VD(id=vid, position=pos, speed=speed, angle=angle, type="vehicle")
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
        ]
        args.extend(["--no-warnings", "false" if self.warnings else "true"])
        #args.extend(["--lateral-resolution", "0.1" ])

        if self.emergency_insertions:
            args.extend(["--emergency-insert", "true"])
        args.append('--start')
        _click.echo(f"{_Fore.GREEN}Starting SUMO with command: {' '.join(args)}{_Style.RESET_ALL}")
        _traci.start(args)
        laneIds = _traci.lane.getIDList()
        self.max_speed_per_lane = {lid: _traci.lane.getMaxSpeed(lid) for lid in laneIds}
        self.baseline_speed_per_lane = self.max_speed_per_lane.copy()

        for pn in range(self.total_packs):
            lb = _MLB()
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
            self.plabels.append(lb)
        
        _traci.close() 

    def dumpExpanded(self, filepath:_Path):
        with open(filepath.resolve(), "w") as fv:
            fv.write("PackId, " + ", ".join([label.name for label in _LE]) + "\n")
            for pn, lb in enumerate(self.plabels):
                fv.write(f"{pn}, " + ", ".join(map(lambda x: "1" if x else "0", lb.getExpanded())) + "\n")


    def dumpEncoded(self, filepath:_Path):
        with open(filepath.resolve(), "w") as fe:
            fe.write("PackId, MLBEncoded\n")
            for pn, lb in enumerate(self.plabels):
                fe.write(f"{pn}, {lb.getEncoded()}\n")

    def dumpVerbose(self, filepath:_Path):
        with open(filepath.resolve(), "w") as fv:
            fv.write("PackId, Labels\n")
            for pn, lb in enumerate(self.plabels):
                fv.write(f"{pn}, " + ", ".join(lb.getLabels(short=True)) + "\n")

    def dumpPandasPacks(self, dirpath:_Path, fname:str,*,format:_Lit["csv","parquet","npy"]="csv"):
        filepath = dirpath / f"{fname}.{format}"
        match format:
            case "csv":
                self.packs_df.to_csv(filepath.resolve(), index=False)
            case "parquet":
                self.packs_df.to_parquet(filepath.resolve(), index=False)
            case "npy":
                npy_data = self.packs_df.to_records(index=False)
                _np.save(filepath.resolve(), npy_data)

@_click.command()
@_click.option('--gui','-g', is_flag=True, default=False, help='Run SUMO with GUI')
@_click.option('--no-warnings', is_flag=True, default=False, help='Suppress SUMO warnings.')
@_click.option('--no-emergency-insertions', is_flag=True, default=False, help='Disable insertion of emergency vehicles during simulation (default: False).')
@_click.option('--step-len','-s', type=float, default=0.2, help='Length of each simulation step in seconds (default: 0.2s).')
@_click.option('--pack-size','-p', type=int, default=20, help='Number of frames in each pack (default: 20).')
@_click.option('--sim-time','-t', type=float, default=500.0, help='Total simulation time in seconds (default: 500s).')
@_click.option('--on-collision', type=_click.Choice([e.value for e in CollisionAction]), default=CollisionAction.TELEPORT.value, help='Action to take on collision (default: remove).')
@_click.option('-om', '--output-mode', 'output_mode', type=str, default='e', help='Output mode for pack labels: combination of [e]ncoded, [x]panded, [v]erbose (default: [e]).')
@_click.option('--outdir', type=_click.Path(file_okay=False, dir_okay=True, writable=True), default=None, help='Output directory for label files (default: ./plabels).')
@_click.option('--delay', '-d', type=float, default=None, help='Delay in ms between simulation steps (default: no delay).')
@_click.argument('cfg_path', type=_click.Path(exists=True), nargs=1)
def runSimulation(gui, no_warnings, no_emergency_insertions, step_len, pack_size, sim_time, on_collision, cfg_path, output_mode,outdir, delay):
    # match output_mode with regex
    if _re.fullmatch(r'[exv]+', output_mode) is None:
        raise _click.BadParameter("Output mode must be a combination of [e]ncoded, [x]panded, [v]erbose (e.g., 'ex', 'v', 'exv').")
    
    sumo_cfg = _SCFG(_Path(cfg_path))

    if sumo_cfg.step_length_s is not None:
        step_len = sumo_cfg.step_length_s
    if sumo_cfg.duration_s is not None:
        sim_time = sumo_cfg.duration_s

    controller = TraciController(
        gui=gui,
        sumo_cfg=sumo_cfg,
        step_len=step_len,
        frame_pack_size=pack_size,
        sim_time_s=sim_time,
        on_collision=CollisionAction(on_collision),
        warnings = not no_warnings,
        emergency_insertions = not no_emergency_insertions,
        delay=delay
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

    controller.dumpPandasPacks(outdir, "pdata", format="parquet")
    _click.echo(f"- Pack data dumped to {outdir / 'pdata.parquet'}")

__all__ = ['runSimulation', 'TraciController', 'CollisionAction']