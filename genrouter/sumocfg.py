from pathlib import Path as _Path
from xml.etree import ElementTree as _ET

class SumoCfg:
    sumocfg_file:_Path
    net_file:_Path
    routes_file:_Path
    duration_s:int
    step_length_s:float

    def getTag(self,from_element:_ET.Element, tag_name:str,*,check=False)->_ET.Element:
        res = from_element.find(tag_name)
        if check and res is None:
            raise ValueError(f"Tag <{from_element}/> in SUMO config file {self.sumocfg_file} does not contain a valid <{tag_name}/> tag")
        return res
        
    def checkAndGetAttr(self,from_element:_ET.Element, attr_name:str)->str:
        res = from_element.attrib.get(attr_name,None)
        if res is None:
            raise ValueError(f"Tag <{from_element}/> in SUMO config file {self.sumocfg_file} does not contain a valid attribute '{attr_name}'")
        return res

    

    def __init__(self, sumocfg_path: _Path):
        self.sumocfg_file = sumocfg_path.resolve()
        rt = _ET.parse(self.sumocfg_file).getroot()
        input_tag = self.getTag(rt,'input', check=True)
        net_tag = self.getTag(input_tag,'net-file', check=True)
        routes_tag = self.getTag(input_tag,'route-files', check=True)

        netfname = self.checkAndGetAttr(net_tag,'value')
        routesfname = self.checkAndGetAttr(routes_tag,'value')
        self.net_file = (self.sumocfg_file.parent / netfname).resolve()
        self.routes_file = (self.sumocfg_file.parent / routesfname).resolve()

        time_tag = self.getTag(rt,'time')
        if time_tag is not None:
            begin_tag= self.getTag(time_tag,'begin')
            end_tag= self.getTag(time_tag,'end')
            steplen_tag = self.getTag(time_tag,'step-length')

            if begin_tag is not None and end_tag is not None:
                begin_s = int(self.checkAndGetAttr(begin_tag,'value'))
                end_s = int(self.checkAndGetAttr(end_tag,'value'))
                self.duration_s = end_s - begin_s

            if steplen_tag is not None:
                self.step_length_s = float(self.checkAndGetAttr(steplen_tag,'value'))

__all__ = ["SumoCfg"]