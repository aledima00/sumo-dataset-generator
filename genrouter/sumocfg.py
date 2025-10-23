from pathlib import Path as _Path
from xml.etree import ElementTree as _ET

def getValueOrNone(from_elm:_ET.Element):
    if from_elm is None or 'value' not in from_elm.attrib:
        return None
    else:
        return from_elm.attrib['value']
    
class SumoCfg:
    sumocfg_file:_Path
    __tree: _ET.ElementTree

    def __getOrNone(self, *pathlike_args):
        cur = self.__tree.getroot()
        for tag in pathlike_args:
            if cur is None:
                return None
            cur = cur.find(tag)
        return cur
    
    def __getOrCreate(self, *pathlike_args)->_ET.Element:
        cur = self.__tree.getroot()
        for tag in pathlike_args:
            elm = cur.find(tag)
            if elm is None:
                elm = _ET.SubElement(cur, tag)
            cur = elm
        return cur

    @property
    def net_file(self)->_Path:
        netfile_elm = self.__getOrNone('input','net-file')
        netFname = getValueOrNone(netfile_elm)
        return None if netFname is None else (self.sumocfg_file.parent / netFname).resolve()
    
    @net_file.setter
    def net_file(self,new_netfile:_Path):
        netfile_elm = self.__getOrCreate('input','net-file')
        netfile_elm.attrib['value'] = str(new_netfile.relative_to(self.sumocfg_file.parent))
        
    @property
    def routes_file(self)->_Path:
        routefile_elm = self.__getOrNone('input','route-files')
        routeFname = getValueOrNone(routefile_elm)
        return (self.sumocfg_file.parent / routeFname).resolve() if routeFname is not None else None
    
    @routes_file.setter
    def routes_file(self,new_routefile:_Path):
        routefile_elm = self.__getOrCreate('input','route-files')
        routefile_elm.attrib['value'] = str(new_routefile.relative_to(self.sumocfg_file.parent))
    
    @property
    def duration_s(self)->float|None:
        begin_elm = self.__getOrNone('time','begin')
        end_elm = self.__getOrNone('time','end')
        begin_val = getValueOrNone(begin_elm)
        end_val = getValueOrNone(end_elm)
        if begin_val is None or end_val is None:
            return None
        begin_s = float(begin_val)
        end_s = float(end_val)
        return end_s - begin_s
    
    @duration_s.setter
    def duration_s(self,new_duration_s:float):
        begin_elm = self.__getOrCreate('time','begin')
        end_elm = self.__getOrCreate('time','end')
        if 'value' not in begin_elm.attrib:
            begin_elm.attrib['value'] = '0'
        begin_s = float(begin_elm.attrib['value'])
        end_elm.attrib['value'] = str(new_duration_s + begin_s)
    
    @property
    def step_length_s(self)->float|None:
        steplen_elm = self.__getOrNone('time','step-length')
        steplen_val = getValueOrNone(steplen_elm)
        return float(steplen_val) if steplen_val is not None else None
    
    @step_length_s.setter
    def step_length_s(self,new_steplen_s:float):
        steplen_elm = self.__getOrCreate('time','step-length')
        steplen_elm.attrib['value'] = str(new_steplen_s)

    def __init__(self, sumocfg_path: _Path):
        self.sumocfg_file = sumocfg_path.resolve()
        self.__tree = _ET.parse(self.sumocfg_file)
        if self.__tree.getroot() is None:
            raise ValueError(f"SUMO config file {self.sumocfg_file} is not a valid XML file")
        
    def save(self):
        self.__tree.write(self.sumocfg_file)

__all__ = ["SumoCfg"]