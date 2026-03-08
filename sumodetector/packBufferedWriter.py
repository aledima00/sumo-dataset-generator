from pathlib import Path as _Path
from .labels import MultiLabel as _MLB
from .pack import PackSchema as _PKS, pack2pandas as _p2df, Frame as _FR


import pandas as _pd

import pyarrow as _pa
import pyarrow.parquet as _pq
from collections import deque as _dq
from typing import TypeAlias as _TA



class PackBufferedWriter:
    FramesListType: _TA = list[tuple[_FR,_MLB]]
    FramesDequeType: _TA = _dq[tuple[_FR,_MLB]]
    class FramesBuffer:
        """
        \\| Pack1... \\| Pack2... \\|
        """
        def __init__(self,frames_per_pack:int,packBuffer:'PackBufferedWriter'):
            self.frames_per_pack = frames_per_pack
            self.packBuffer = packBuffer
            self.frames_buf: PackBufferedWriter.FramesDequeType = _dq()

        def len(self)->int:
            return len(self.frames_buf)
        def isFull(self)->bool:
            return len(self.frames_buf) >= self.frames_per_pack*2
        def isReadyPack(self)->bool:
            return len(self.frames_buf) >= self.frames_per_pack


        def popFlistFromEnd(self)->'PackBufferedWriter.FramesListType':
            frameslist = list(self.frames_buf)[-self.frames_per_pack:]
            for _ in range(self.frames_per_pack):
                self.frames_buf.pop()
            return frameslist
        
        def popFlistFromBeginning(self)->'PackBufferedWriter.FramesListType':
            frameslist = list(self.frames_buf)[:self.frames_per_pack]
            for _ in range(self.frames_per_pack):
                self.frames_buf.popleft()
            return frameslist
        
        def appendFrame(self, frame:_FR, mlb:_MLB, triggered:bool):
            self.frames_buf.append((frame, mlb))
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


                
    def __init__(self,save_dirpath:_Path,num_packs_buffered:int, frames_per_pack:int,*, startPackId:int=1):
        self.packs_df = _pd.DataFrame()
        self.labels_per_pid_df = _pd.DataFrame()
        self.num_packs_buffered = num_packs_buffered
        self.cnt = 0

        self.pkpath = save_dirpath / "packs.parquet"
        self.lbpath = save_dirpath / "labels.parquet"
        self.vipath = save_dirpath / "vinfo.parquet"
        self.pkwriter = _pq.ParquetWriter(str(self.pkpath), _PKS())
        
        self.last_pack_id = startPackId-1

        self.frames_buffer = PackBufferedWriter.FramesBuffer(frames_per_pack=frames_per_pack, packBuffer=self)

    def appendPackByFlist(self,framesList:FramesListType):
        newpid = self.last_pack_id+1
        dataList, mlbList = zip(*framesList)

        p = _p2df(newpid, dataList)
        if p is not None:
            mlb = _MLB.mergeList(mlbList)
            self.__appendPack(p)
            self.__appendMlb(mlb, newpid)
            self.last_pack_id = newpid

    def __appendPack(self, packdf:_pd.DataFrame):
        self.packs_df = _pd.concat([self.packs_df, packdf], ignore_index=True)
        if self.cnt >= self.num_packs_buffered:
            self.flushToDisk()
        else:
            self.cnt += 1

    def __appendMlb(self,mlb:_MLB,pid:int):
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