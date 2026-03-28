from math import floor as _floor
import sumolib as _sumolib
import traci as _traci
from typing import Literal as _Lit
from pathlib import Path as _Path
from .labels import LabelsEnum as _LE, MultiLabel as _MLB
from .map import MapParser as _MP
from .sumocfg import SumoCfg as _SCFG
from .pack import PackSchema as _PKS, pack2pandas as _p2df, Frame as _FR, VehicleData as _VD, VInfo as _VI, PInfo as _PI
from .tup import TraciUpdater as _TraciUpdater, SimpleTraciUpdater as _SimpleTraciUpdater
from .packBufferedWriter import PackBufferedWriter as _PBW, OpMode as _OpMode

from colorama import Fore as _Fore, Style as _Style
import re as _re
import time as _t
import numpy as _np
import pandas as _pd
import multiprocessing as _mp
import sys as _sys
import os as _os

from dataclasses import dataclass as _dc

@_dc
class FrameVState:
    lane_id: str
    lane_id_no_junc_intlane: str|None = None
    leader_id: str|None = None
    ebk_time_s: float = 0.0
    

CollisionAction = _Lit["teleport", "warn", "none", "remove"]

def getStTypeFromVTypeID(vtype_id:str,*,default:int|None=None)->int:
    match = _re.search(r"^ST(\d+)(_|$)", vtype_id)
    if match:
        return int(match.group(1))
    elif default is not None:
        return default
    else:
        raise ValueError(f"Invalid vType ID format: {vtype_id}")


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
    total_frames:int

    # thresholds
    ebk_time_threshold_s:float
    merge_speed_threshold:float
    slowdown_traffic_threshold:float
    traffic_jam_min_size:int

    # state variables
    max_speed_per_lane:dict[str,float]
    baseline_speed_per_lane:dict[str,float]
    th_ebk_per_vt:dict[str,float]

    last_step_vstates:dict[str, FrameVState]

    # simulation-wise info
    vinfo_per_vid_df  :_pd.DataFrame

    map_parser:_MP
    cfg:_SCFG
    pbw_opmode: _OpMode


    def __init__(self,*,gui:bool,sumo_cfg:_SCFG,frame_pack_size:int,sim_time_s:float,start_time_s:float,on_collision:CollisionAction='none',warnings:bool,emergency_insertions:bool,delay:float=None,active_labels:set[_LE],printfunc=None,tlog:bool=False,traci_updater:_TraciUpdater=None, pbw_opmode:_OpMode="absolute"):
        self.gui = gui
        self.cfg = sumo_cfg
        self.step_len = sumo_cfg.step_length_s
        self.frame_pack_size = frame_pack_size
        self.start_time_s = start_time_s
        self.sim_time_s = sim_time_s
        self.on_collision = on_collision
        self.warnings = warnings
        self.emergency_insertions = emergency_insertions
        self.delay = delay

        self.sumobin = _sumolib.checkBinary('sumo-gui' if gui else 'sumo')
        self.total_frames = _floor(self.sim_time_s / self.step_len)

        self.map_parser = _MP(str(self.cfg.net_file))

        # TODO:CHECK these values
        self.th_ebk_per_vt = dict()
        self.ebk_prop_threshold = 0.50
        self.ebk_time_threshold_s = 0.05 #TODO:CHECK if it's ok to use time-based threshold for this
        self.merge_speed_threshold = 0.3
        self.slowdown_traffic_threshold = 0.1
        self.traffic_jam_min_size = 8

        # last step vstates
        self.last_step_vstates = dict()

        # simulation-wise info
        self.vinfo_per_vid_df  = _pd.DataFrame()

        # utilities
        self.active_labels = active_labels
        self.print = printfunc if printfunc is not None else (lambda x: None)
        self.__tlog_enabled = tlog

        # traci updater
        self.traci_updater = traci_updater if traci_updater is not None else _SimpleTraciUpdater()

        # pack buffered writer opmode
        self.pbw_opmode = pbw_opmode

    def tlog(self, val:str):
        if self.__tlog_enabled:
            self.print(f"{_Fore.MAGENTA}[{_traci.simulation.getTime()}] {val}{_Style.RESET_ALL}")


    def __getVtEbkTh(self, vtid:str)->float:
        if vtid not in self.th_ebk_per_vt:
            v_decel = _traci.vehicle.getDecel(vtid)
            v_em_decel = _traci.vehicle.getEmergencyDecel(vtid)
            threshold_decel = v_decel + (v_em_decel - v_decel) * self.ebk_prop_threshold
            self.th_ebk_per_vt[vtid] = threshold_decel
        return self.th_ebk_per_vt[vtid]
    
    @staticmethod
    def __getVehEdge(vid:str)->str|None:
        if vid is None or vid not in _traci.vehicle.getIDList():
            return None
        lid = _traci.vehicle.getLaneID(vid)
        return _traci.lane.getEdgeID(lid) if lid is not None else None

    @staticmethod
    def __getRealEdgeLeader(vid:str)->str|None:
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
        """
        Updates the internal state at the end of each simulation step, keeping track of history of PREVIOUS STEPS.
        """
        step_vehicles = _traci.vehicle.getIDList()

        # delete entries from dicts for vehicles that are no longer in the simulation
        self.last_step_vstates = {vid: vstate for vid,vstate in self.last_step_vstates.items() if vid in step_vehicles}

        for vid in step_vehicles:
            if not str(vid).startswith("OBS_"):
                lane_id = _traci.vehicle.getLaneID(vid) 
                leader_id = self.__getRealEdgeLeader(vid)
                nojint_lane_id = lane_id if not self.map_parser.isLaneSpecial(lane_id) else None

                # ebk times
                #vt = _traci.vehicle.getTypeID(vid) # TODO:CHECK if needed
                acc = _traci.vehicle.getAcceleration(vid)
                ebktime = 0.0
                if acc < -self.__getVtEbkTh(vid):
                    current = self.last_step_vstates.get(vid,None)
                    ebktime = (current.ebk_time_s if current is not None else 0.0) + self.step_len

                self.last_step_vstates[vid] = FrameVState(
                    lane_id=lane_id,
                    lane_id_no_junc_intlane=nojint_lane_id,
                    leader_id=leader_id,
                    ebk_time_s=ebktime
                )

    def __checkCollision(self,lb:_MLB) ->bool:
        clist = _traci.simulation.getCollidingVehiclesIDList()
        if len(clist)>0:
            self.tlog(f"Collision detected among vehicles: {clist}")
            lb.setLabel(_LE.COLLISION)
            return True
        return False

    def __checkEmergencyBraking(self,lb:_MLB) ->bool:
        for vid in _traci.vehicle.getIDList():
            if not str(vid).startswith("OBS_"):
                #vt = _traci.vehicle.getTypeID(vid)
                acc = _traci.vehicle.getAcceleration(vid)

                if acc < -self.__getVtEbkTh(vid):
                    ls_vstate = self.last_step_vstates.get(vid,None)
                    tot_time = (ls_vstate.ebk_time_s if ls_vstate is not None else 0.0) + self.step_len
                    if tot_time >= self.ebk_time_threshold_s:
                        self.tlog(f"Emergency Braking detected for vehicle: {vid}")
                        lb.setLabel(_LE.EMERGENCY_BRAKING)
                        return True
        return False
            
    def __checkObstacles(self,lb:_MLB) ->bool:
        for vid in _traci.vehicle.getIDList():
            if str(vid).startswith("OBS_"):
                self.tlog(f"Obstacle {vid} detected in simulation.")
                lb.setLabel(_LE.OBSTACLE_IN_ROAD)
                return True
        return False
            
    def __checkSlowdown(self,lb:_MLB) ->bool:
        for laneId in self.max_speed_per_lane.keys():

            vehs_in_lane:tuple[str] = _traci.lane.getLastStepVehicleIDs(laneId)
            if vehs_in_lane is None or len(vehs_in_lane) < self.traffic_jam_min_size:
                continue

            avg_speed = _np.mean([_traci.vehicle.getSpeed(vid) for vid in vehs_in_lane])

            ratio = avg_speed / self.baseline_speed_per_lane[laneId]
            if ratio < self.slowdown_traffic_threshold:
                self.tlog(f"Traffic jam detected on lane {laneId} with average speed {avg_speed:.2f} m/s ({ratio*100:.1f}% of baseline).")
                lb.setLabel(_LE.SLOWDOWN)
                return True
        return False
        

    def __checkLCLM(self,lb:_MLB) ->bool:
        for vid in _traci.vehicle.getIDList():
            if not str(vid).startswith("OBS_"):
                lane_id = _traci.vehicle.getLaneID(vid)
                ls_vstate = self.last_step_vstates.get(vid,None)
                prev_lane_id = ls_vstate.lane_id if ls_vstate is not None else None
                if prev_lane_id is not None and lane_id != prev_lane_id:
                    e1id = _traci.lane.getEdgeID(prev_lane_id)
                    e2id = _traci.lane.getEdgeID(lane_id)
                    if e1id == e2id:
                        # generic lc situation
                        is_lc_lm = self.map_parser.checkIfLcLm(prev_lane_id,lane_id)
                        if is_lc_lm:
                            # lane merge situation
                            self.tlog(f"Vehicle {vid} performed Lane Change corresponding to Lane Merge from lane {prev_lane_id} to {lane_id} on edge {e1id}.")
                            lb.setLabel(_LE.LANE_MERGE)
                        else:
                            # simple lane change
                            self.tlog(f"Vehicle {vid} changed lane from {prev_lane_id} to {lane_id} on edge {e1id}.")
                            lb.setLabel(_LE.LANE_CHANGE)
                        return True
        return False
                    
    def __checkOvertake(self,lb:_MLB) ->bool:
        for vid in _traci.vehicle.getIDList():
            if not str(vid).startswith("OBS_"):
                ls_vstate = self.last_step_vstates.get(vid,None)
                old_leader_id = ls_vstate.leader_id if ls_vstate is not None else None
                current_leader_id = self.__getRealEdgeLeader(vid)
                if old_leader_id is not None and current_leader_id != old_leader_id and (self.__getVehEdge(vid) == self.__getVehEdge(old_leader_id)):
                    lb.setLabel(_LE.OVERTAKE)
                    self.tlog(f"Detected Overtake of Vehicle {vid} on {old_leader_id}")
                    return True
        return False
                        
    def __checkTurn(self,lb:_MLB) ->bool:
        for vid in _traci.vehicle.getIDList():
            if not str(vid).startswith("OBS_"):
                lane_id = _traci.vehicle.getLaneID(vid)
                ls_vstate = self.last_step_vstates.get(vid,None)
                prev_lane_id = ls_vstate.lane_id_no_junc_intlane if ls_vstate is not None else None
                if prev_lane_id is not None and lane_id is not None and lane_id != prev_lane_id and (not self.map_parser.isLaneSpecial(lane_id)):
                    cont_lane_id = self.map_parser.getContToLaneId(from_lane_id=prev_lane_id)
                    if cont_lane_id is None or lane_id != cont_lane_id:
                        # turning detected
                        lb.setLabel(_LE.TURN_INTENT)
                        self.tlog(f"Vehicle {vid} performed turn from lane {prev_lane_id} to {lane_id}.")
                        return True
        return False
                    
    def __checkFrameByLabel(self,lbname:_LE,mlb:_MLB)->bool:
        if lbname == _LE.LANE_CHANGE or lbname == _LE.LANE_MERGE:
            return self.__checkLCLM(mlb)
        elif lbname == _LE.OVERTAKE:
            return self.__checkOvertake(mlb)
        elif lbname == _LE.EMERGENCY_BRAKING:
            return self.__checkEmergencyBraking(mlb)
        elif lbname == _LE.TURN_INTENT:
            return self.__checkTurn(mlb)
        elif lbname == _LE.COLLISION:
            return self.__checkCollision(mlb)
        elif lbname == _LE.OBSTACLE_IN_ROAD:
            return self.__checkObstacles(mlb)
        elif lbname == _LE.SLOWDOWN:
            return self.__checkSlowdown(mlb)
        else:
            raise ValueError(f"Unknown label {lbname}")
        
    def __checkFrame(self,mlb:_MLB) ->bool:
        # trigger: at least one label detected
        flag = False
        for label in self.active_labels:
            flag |= self.__checkFrameByLabel(label, mlb)
        return flag

    
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
    
    def computeFrame(self) -> _FR:
        frame = _FR()
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
                sttype = getStTypeFromVTypeID(vtid, default=5) # default to car
                self.tryAddVInfo(vid,w=width,l=length,stType=sttype)
                vdata = _VD(id=vid, position=pos, speed=speed, angle=angle)
                frame.vehicles.append(vdata)
        return frame
    
    def run(self,save_dirpath:_Path,progress_queue:_mp.Queue=None):

        pbw = _PBW(
            save_dirpath=save_dirpath,
            num_packs_buffered=2000,
            frames_per_pack=self.frame_pack_size,
            startPackId=0,
            opmode=self.pbw_opmode
        )

        # define parameters and start simulation
        args = [
            self.sumobin,
            "-c", str(self.cfg.sumocfg_file),
            "--collision.action", self.on_collision,
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
        #self.print(f"{_Fore.WHITE}{_Style.DIM}Starting SUMO (with command: {' '.join(args)}){_Style.RESET_ALL}")
        tmp = _sys.stdout
        _sys.stdout = open(_os.devnull, 'w')
        _traci.start(args)
        _sys.stdout = tmp

        # buffers
        laneIds = _traci.lane.getIDList()
        self.max_speed_per_lane = {lid: _traci.lane.getMaxSpeed(lid) for lid in laneIds}
        self.baseline_speed_per_lane = self.max_speed_per_lane.copy()
        mlb = _MLB()

        if self.start_time_s > 0.0:
            self.tlog(f"Skipping to start time {self.start_time_s}s...")
            self.traci_updater.jumpTo(self.start_time_s-self.step_len)
            self.__updateState()
            self.traci_updater.update()

        # -------------------------- main simulation loop --------------------------
        for fnum in range(self.total_frames):
            mlb.clear()
            #FIXME: double update call???
            self.traci_updater.update()
            triggered = self.__checkFrame(mlb)

            frameData = self.computeFrame() #TODO:CHECK slowing point
            pbw.appendFrame(frameData, mlb, triggered)

            # end of frame analysis: update and wait for next
            self.__updateState()
            if self.delay is not None:
                _t.sleep(self.delay)

            if progress_queue is not None:
                progress_queue.put(1)
        
        tend = _traci.simulation.getTime()
        self.tlog(f"Simulation ended at time {tend}, closing SUMO...")
        _traci.close()

        # save labels and vinfo to related .parquet files
        pbw.close(dumpLabels=True,dumpedVinfo=self.vinfo_per_vid_df)

__all__ = ['TraciController', 'CollisionAction']