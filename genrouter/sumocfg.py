from pathlib import Path as _Path
from xml.etree import ElementTree as _ET

def getValueOrNone(from_elm:_ET.Element):
    if from_elm is None or 'value' not in from_elm.attrib:
        return None
    else:
        return from_elm.attrib['value']
    

class MissingParamForSumoCfg(Exception):
    def __init__(self, param:str):
        super().__init__()
        self.message = f"Missing Parameter '{param}' for Configuration: please provide it with the dedicated CLI option or edit the SUMO config file directly."
    
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
    def duration_s(self)->int|None:
        begin_elm = self.__getOrNone('time','begin')
        end_elm = self.__getOrNone('time','end')
        begin_val = getValueOrNone(begin_elm)
        end_val = getValueOrNone(end_elm)
        if begin_val is None or end_val is None:
            return None
        begin_s = int(begin_val)
        end_s = int(end_val)
        return end_s - begin_s
    
    @duration_s.setter
    def duration_s(self,new_duration_s:int):
        begin_elm = self.__getOrCreate('time','begin')
        end_elm = self.__getOrCreate('time','end')
        if 'value' not in begin_elm.attrib:
            begin_elm.attrib['value'] = '0'
        begin_s = int(begin_elm.attrib['value'])
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

    def __init__(self, sumocfg_path: _Path, split: bool = False):
        self.sumocfg_file = sumocfg_path.resolve()
        if sumocfg_path.exists():
            self.__tree = _ET.parse(self.sumocfg_file)
            if self.__tree.getroot() is None:
                raise ValueError(f"SUMO config file {self.sumocfg_file} is not a valid XML file")
        else:
            root = _ET.Element('sumoConfiguration')
            root.attrib["xmlns:xsi"] = "http://www.w3.org/2001/XMLSchema-instance"
            root.attrib["xsi:noNamespaceSchemaLocation"] = "http://sumo.dlr.de/xsd/sumoConfiguration.xsd"
            self.__tree = _ET.ElementTree(root)
        if self.net_file is None:
            print(f"Warning: net-file not specified in SUMO config file, setting default to '{'..' if split else '.'}/map.net.xml'")
            self.net_file = (sumocfg_path.parent / (".." if split else ".") / "map.net.xml")
        if self.routes_file is None:
            print("Warning: route-filename not specified in SUMO config file, setting default to './routes.rou.xml'")
            self.routes_file = (sumocfg_path.parent / "routes.rou.xml")
        
    def save(self):
        if not self.sumocfg_file.parent.exists():
            self.sumocfg_file.parent.mkdir(parents=True, exist_ok=True)

        _ET.indent(self.__tree, space="  ", level=0)
        self.__tree.write(self.sumocfg_file,encoding='UTF-8',xml_declaration=True)

    def overwrite(self,*, time:int=None, route_filename=None, net_filename=None, step_len:float=None):
        if time is not None:
            self.duration_s = time
        if route_filename is not None:
            self.routes_file = _Path(route_filename).resolve()
        if net_filename is not None:
            self.net_file = _Path(net_filename).resolve()
        if step_len is not None:
            self.step_length_s = step_len

    def checkReqParams(self):
        if self.duration_s is None:
            raise MissingParamForSumoCfg('time')
        if self.routes_file is None:
            raise MissingParamForSumoCfg('route-filename')
        if self.net_file is None:
            raise MissingParamForSumoCfg('net-filename')
        if self.step_length_s is None:
            raise MissingParamForSumoCfg('step-len')

__all__ = ["SumoCfg"]