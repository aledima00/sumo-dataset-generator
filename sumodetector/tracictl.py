from math import floor as _floor
import sumolib as _sumolib
import traci as _traci
from typing import Literal as _Lit
from pathlib import Path as _Path
from .labels import LabelsEnum as _LE, MultiLabel as _MLB
from .map import MapParser as _MP, PedestrianAreaType as _PAT
from .sumocfg import SumoCfg as _SCFG
from .pack import PackData as _PKD, FrameData as _FD, VehicleData as _VD, VInfo as _VI, PInfo as _PI
from colorama import Fore as _Fore, Style as _Style
import re as _re
import time as _t
import numpy as _np
import pandas as _pd
import multiprocessing as _mp
import sys as _sys
import os as _os

import pyarrow as _pa
import pyarrow.parquet as _pq
    

CollisionAction = _Lit["teleport", "warn", "none", "remove"]

def getStTypeFromVTypeID(vtype_id:str)->int:
    match = _re.search(r"^ST(\d+)(_|$)", vtype_id)
    if match:
        return int(match.group(1))
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


    def __init__(self,*,gui:bool,sumo_cfg:_SCFG,frame_pack_size:int,sim_time_s:float,start_time_s:float,on_collision:CollisionAction='none',warnings:bool,emergency_insertions:bool,delay:float=None,active_labels:set[_LE],printfunc=None,tlog:bool=False):
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
        self.total_steps = _floor(self.sim_time_s / self.step_len)
        self.total_packs = _floor(self.total_steps / self.frame_pack_size)

        self.map_parser = _MP(str(self.cfg.net_file))

        # TODO:CHECK these values
        self.acc_braking_threshold = -2.0 # m/s²
        self.slowdown_traffic_threshold = 0.1
        self.merge_speed_threshold = 0.3
        self.traffic_jam_min_size = 8
        self.braking_min_count = 4

        # state
        self.vehs_lanes = dict()
        self.vehs_lanes_no_junc_intlane = dict()
        self.vehs_leaders = dict()
        self.labels_per_pid_df = _pd.DataFrame()
        self.vinfo_per_vid_df = _pd.DataFrame()

        self.active_labels = active_labels
        self.print = printfunc if printfunc is not None else (lambda x: None)
        self.__tlog_enabled = tlog

    def tlog(self, val:str):
        if self.__tlog_enabled:
            self.print(f"{_Fore.MAGENTA}[{_traci.simulation.getTime()}] {val}{_Style.RESET_ALL}")


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
    
    def __checkCollision(self,lb:_MLB)->bool:
        if lb.checkLabelDone(_LE.COLLISION):
            return True
        clist = _traci.simulation.getCollidingVehiclesIDList()
        if len(clist)>0:
            self.tlog(f"Collision detected among vehicles: {clist}")
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
                    self.tlog(f"Braking detected for vehicles: {vbs}")
                    lb.setLabel(_LE.BRAKING)
                    return True
            
    def __checkObstacles(self,lb:_MLB):
        if lb.checkLabelDone(_LE.OBSTACLE_IN_ROAD):
            return True
        for vid in _traci.vehicle.getIDList():
            if str(vid).startswith("OBS_"):
                self.tlog(f"Obstacle {vid} detected in simulation.")
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
                self.tlog(f"Traffic jam detected on lane {laneId} with average speed {avg_speed:.2f} m/s ({ratio*100:.1f}% of baseline).")
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
                            self.tlog(f"Vehicle {vid} changed lane from {prev_lane_id} to {lane_id} on edge {e1id}.")
                        if not lb.checkLabelDone(_LE.LANE_MERGE):
                            is_lc_lm = self.map_parser.checkIfLcLm(prev_lane_id,lane_id)
                            if is_lc_lm:
                                lb.setLabel(_LE.LANE_MERGE)
                                self.tlog(f"Vehicle {vid} performed Lane Change corresponding to Lane Merge from lane {prev_lane_id} to {lane_id} on edge {e1id}.")
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
                    self.tlog(f"Detected Overtake of Vehicle {vid} on {old_leader_id}")
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
                        self.tlog(f"Vehicle {vid} performed turn from lane {prev_lane_id} to {lane_id}.")
                        return True
                   
    def __checkPedestrianInRoad(self,lb:_MLB):
        if lb.checkLabelDone(_LE.PEDESTRIAN_IN_ROAD):
            return True
        for pid in _traci.person.getIDList():
            laneid=_traci.person.getLaneID(pid)
            is_pedestrian_area, area_type = self.map_parser.isPedestrianArea(laneid)
            if not is_pedestrian_area:
                lb.setLabel(_LE.PEDESTRIAN_IN_ROAD)
                self.tlog(f"Detected Pedestrian {pid} in road lane {laneid}")
                return True
            elif area_type==_PAT.CROSSING_TLS:
                # if crossing with tls, further check if it has right of way
                links = _traci.lane.getLinks(laneid, extended=True)
                for (succLane, hasPrio, isOpen, hasFoe, *_) in links:
                    # isOpen=True => semaforo verde o priorità libera
                    # hasFoe=False => nessuna lane conflittuale con precedenza
                    if (not isOpen) or hasFoe:
                        lb.setLabel(_LE.PEDESTRIAN_IN_ROAD)
                        self.tlog(f"Detected Pedestrian {pid} in crossing with traffic light lane {laneid} without right of way")
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
    
    def run(self,save_dirpath:_Path,progress_queue:_mp.Queue=None):

        pkpath = save_dirpath / "packs.parquet"
        pkwriter = _pq.ParquetWriter(str(pkpath), _PKD.pyarrowSchema())
        lbpath = save_dirpath / "labels.parquet"
        vipath = save_dirpath / "vinfo.parquet"

        packs_buffer_df = _pd.DataFrame()
        # TODO: finish implementing buffering strategy
        max_pbuf_cnt = 2000
        cur_pbuf_cnt = 0

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
        laneIds = _traci.lane.getIDList()
        self.max_speed_per_lane = {lid: _traci.lane.getMaxSpeed(lid) for lid in laneIds}
        self.baseline_speed_per_lane = self.max_speed_per_lane.copy()
        lb = _MLB(active_labels=self.active_labels)

        if self.start_time_s > 0.0:
            self.tlog(f"Skipping to start time {self.start_time_s}s...")
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

            pp = pack.asPandas()
            if pp is not None:
                packs_buffer_df = _pd.concat([packs_buffer_df, pp], ignore_index=True)
                self.labels_per_pid_df = _pd.concat([self.labels_per_pid_df, lb.asPandas(pn)], ignore_index=True)
                cur_pbuf_cnt += 1

            if cur_pbuf_cnt >= max_pbuf_cnt:
                # flush buffer to disk
                pks_tbl = _pa.Table.from_pandas(packs_buffer_df)
                pkwriter.write_table(pks_tbl)
                packs_buffer_df = _pd.DataFrame()
                cur_pbuf_cnt = 0

            if progress_queue is not None:
                progress_queue.put(1)
        
        # empties buffer if not empty
        if cur_pbuf_cnt > 0:
            pks_tbl = _pa.Table.from_pandas(packs_buffer_df)
            pkwriter.write_table(pks_tbl)
            packs_buffer_df = _pd.DataFrame()
            cur_pbuf_cnt = 0
        
        tend = _traci.simulation.getTime()
        self.tlog(f"Simulation ended at time {tend}, closing SUMO...")
        _traci.close() 

        # save labels and vinfo to related .parquet files
        self.labels_per_pid_df.to_parquet(lbpath, index=False)
        self.vinfo_per_vid_df.to_parquet(vipath, index=False)
        if pkwriter is not None:
            pkwriter.close()



        

__all__ = ['TraciController', 'CollisionAction']