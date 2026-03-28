from pathlib import Path as _Path
from typing import Literal as _Lit, TypeAlias as _TA

from .labels import MultiLabel as _MLB
from .pack import PackSchema as _PKS, pack2pandas as _p2df, Frame as _FR


import pandas as _pd

import pyarrow as _pa
import pyarrow.parquet as _pq
from collections import deque as _dq
from typing import TypeAlias as _TA


OpMode: _TA = _Lit["dense", "sequential", "absolute"]

class PackBufferedWriter:
    FramesListType: _TA = list[tuple[_FR,_MLB]]
    FramesDequeType: _TA = _dq[tuple[_FR,_MLB]]
    opmode: OpMode
    class FramesBuffer:
        """
        \\| Pack1... \\| Pack2... \\|
        """
        def __init__(self,frames_per_pack:int,packBuffer:'PackBufferedWriter'):
            self.frames_per_pack = frames_per_pack
            self.packBuffer = packBuffer
            self.frames_buf: PackBufferedWriter.FramesDequeType = _dq(maxlen=frames_per_pack) if packBuffer.opmode == "dense" else _dq()

            match packBuffer.opmode:
                case "absolute":
                    def appendCallback(triggered:bool):
                        if triggered:
                            # we have to borrow frames to make a pack with triggered frame as last
                            # if ready we send to PackBufferedWriter, otherwise we flush
                            if self.isReadyPack():
                                flist = self.popFlistFromEnd()
                                self.packBuffer.appendPackByFlist(flist)

                                # check if still remains one complete (case of exactly 2 packs buffered with a triggered frame as last)
                                if self.isReadyPack():
                                    flist = self.popFlistFromBeginning()
                                    self.packBuffer.appendPackByFlist(flist)
                            # flush all frames, if any remains
                            self.frames_buf.clear()
                        elif self.isFull():
                            flist = self.popFlistFromBeginning()
                            self.packBuffer.appendPackByFlist(flist)
                case "dense":
                    def appendCallback(triggered:bool):
                        if self.isReadyPack():
                            flist = self.createFlistFromBeginning() # auto popping
                            self.packBuffer.appendPackByFlist(flist)
                case "sequential":
                    # same callback as absolute, but without flushing the buffer when trigger received without ready pack, to enable multiple triggering frames in a pack.
                    def appendCallback(triggered:bool):
                        if triggered:
                            # we have to borrow frames to make a pack with triggered frame as last
                            # if ready we send to PackBufferedWriter, otherwise we flush
                            if self.isReadyPack():
                                flist = self.popFlistFromEnd()
                                self.packBuffer.appendPackByFlist(flist)

                                # check if still remains one complete (case of exactly 2 packs buffered with a triggered frame as last)
                                if self.isReadyPack():
                                    flist = self.popFlistFromBeginning()
                                    self.packBuffer.appendPackByFlist(flist)
                                # flush all frames, if any remains
                                self.frames_buf.clear()
                        elif self.isFull():
                            flist = self.popFlistFromBeginning()
                            self.packBuffer.appendPackByFlist(flist)
                case _:
                    raise ValueError(f"Unknown operation mode: {packBuffer.opmode}")
            self.appendFrameCallback = appendCallback

        def len(self)->int:
            return len(self.frames_buf)
        
        def isFull(self)->bool:
            """ return True if the buffer is full (2 packs). """
            return len(self.frames_buf) >= self.frames_per_pack*2
        
        def isReadyPack(self)->bool:
            """ return True if the buffer has enough frames to form a complete pack. """
            return len(self.frames_buf) >= self.frames_per_pack


        def popFlistFromEnd(self,*,clear=True)->'PackBufferedWriter.FramesListType':
            """ Pop a pack-long list of frames from the end of the buffer."""
            frameslist = list(self.frames_buf)[-self.frames_per_pack:]
            if clear:
                self.frames_buf.clear()
            else:
                for _ in range(self.frames_per_pack):
                    self.frames_buf.pop()
            return frameslist
        
        def popFlistFromBeginning(self,*,clear=False)->'PackBufferedWriter.FramesListType':
            """ Pop a pack-long list of frames from the beginning of the buffer."""
            frameslist = list(self.frames_buf)[:self.frames_per_pack]
            if clear:
                self.frames_buf.clear()
            else:
                for _ in range(self.frames_per_pack):
                    self.frames_buf.popleft()
            return frameslist
        
        def createFlistFromBeginning(self)->'PackBufferedWriter.FramesListType':
            """ Create a pack-long list of frames from the beginning of the buffer. """
            frameslist = list(self.frames_buf)[:self.frames_per_pack]
            return frameslist
        
        def appendFrame(self, frame:_FR, mlb:_MLB, triggered:bool):
            self.frames_buf.append((frame, mlb))
            self.appendFrameCallback(triggered)
                
    def __init__(self,save_dirpath:_Path,num_packs_buffered:int, frames_per_pack:int,*, startPackId:int=1, opmode:OpMode="absolute"):
        self.packs_df = _pd.DataFrame()
        self.labels_per_pid_df = _pd.DataFrame()
        self.num_packs_buffered = num_packs_buffered
        self.cnt = 0

        self.pkpath = save_dirpath / "packs.parquet"
        self.lbpath = save_dirpath / "labels.parquet"
        self.vipath = save_dirpath / "vinfo.parquet"
        self.pkwriter = _pq.ParquetWriter(str(self.pkpath), _PKS())
        
        self.last_pack_id = startPackId-1

        self.opmode = opmode
        self.frames_buffer = PackBufferedWriter.FramesBuffer(frames_per_pack=frames_per_pack, packBuffer=self)

        match self.opmode:
            case "absolute":
                def computeMlbCallback(mlblist):
                    mlb = _MLB.mergeList(mlblist)
                    return mlb
            case "dense":
                def computeMlbCallback(mlblist):
                    mlb = mlblist[-1] if len(mlblist) > 0 else _MLB()
                    return mlb
            case "sequential":
                def computeMlbCallback(mlblist):
                    mlb = mlblist[-1] if len(mlblist) > 0 else _MLB()
                    return mlb
            case _:
                raise ValueError(f"Unknown operation mode: {self.opmode}")
        self.computeMlbCallback = computeMlbCallback

    def appendPackByFlist(self,framesList:FramesListType):
        """ Append a pack to the buffer by a list of frames and their corresponding multi-labels. """
        newpid = self.last_pack_id+1
        dataList, mlbList = zip(*framesList)

        p = _p2df(newpid, dataList)
        if p is not None:
            mlb = self.computeMlbCallback(mlbList)
            self.__appendPack(p)
            self.__appendMlb(mlb, newpid)
            self.last_pack_id = newpid

    def __appendPack(self, packdf:_pd.DataFrame):
        """ Append a pack dataframe to the buffer, and flush to disk if buffer is full. """
        self.packs_df = _pd.concat([self.packs_df, packdf], ignore_index=True)
        if self.cnt >= self.num_packs_buffered:
            self.flushToDisk()
        else:
            self.cnt += 1

    def __appendMlb(self,mlb:_MLB,pid:int):
        """ Append a mlb to the labels buffer, and flush to disk if buffer is full. """
        self.labels_per_pid_df = _pd.concat([self.labels_per_pid_df, mlb.asPandas(pid)], ignore_index=True)


    def flushToDisk(self):
        pks_tbl = _pa.Table.from_pandas(self.packs_df)
        self.pkwriter.write_table(pks_tbl)
        self.packs_df = _pd.DataFrame()
        self.cnt = 0

    def appendFrame(self, frame:_FR, mlb:_MLB, triggered:bool):
        self.frames_buffer.appendFrame(frame, mlb, triggered)

    def len(self):
        return self.cnt
    def empty(self)->bool:
        return self.cnt == 0

    def close(self,*, dumpLabels:bool, dumpedVinfo:_pd.DataFrame|None):
        if not self.empty():
            self.flushToDisk()
        self.pkwriter.close()
        if dumpLabels:
            self.dumpLabelsDf()
        if dumpedVinfo is not None:
            self.dumpVInfoDf(dumpedVinfo)
        
    def dumpLabelsDf(self):
        return self.labels_per_pid_df.to_parquet(self.lbpath, index=False)
    
    def dumpVInfoDf(self,vinfo_df:_pd.DataFrame):
        return vinfo_df.to_parquet(self.vipath, index=False)

__all__ = ["PackBufferedWriter"]