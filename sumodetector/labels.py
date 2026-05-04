from enum import IntEnum as _IE
import pandas as _pd

class LabelsEnum(_IE):
    LANE_CHANGE = 0
    OVERTAKE = 1
    TURN_INTENT = 2
    COLLISION = 3

shorts ={
    LabelsEnum.LANE_CHANGE: "LCH",
    LabelsEnum.OVERTAKE: "OTK",
    LabelsEnum.TURN_INTENT: "TRN",
    LabelsEnum.COLLISION: "COL"
}

class MultiLabel:
    __encoded_labels:int
    def __init__(self):
        self.__encoded_labels = 0

    def setLabel(self,label:LabelsEnum,value:bool=True):
        if value:
            self.__encoded_labels |= (1 << label.value)
        else:
            self.__encoded_labels &= ~(1 << label.value)
    def getEncoded(self)->int:
        return self.__encoded_labels
    def getExpanded(self)->list[bool]:
        expanded = []
        for label in LabelsEnum:
            expanded.append((self.__encoded_labels & (1 << label.value)) != 0)
        return expanded
    def getLabels(self,short:False)->set[LabelsEnum|str]:
        labels = set()
        for label in LabelsEnum:
            if (self.__encoded_labels & (1 << label.value)) != 0:
                labels.add(label if not short else shorts[label])
        return labels
    def asPandas(self, packID:int) -> _pd.DataFrame:
        return _pd.DataFrame([{
            "PackId": packID,
            "MLBEncoded": self.getEncoded()
        }]).astype({
            "PackId": "uint32",
            "MLBEncoded" : "uint16"
        })
    def clear(self):
        self.__encoded_labels = 0
    @staticmethod
    def mergeList(labels_list:list['MultiLabel']) -> 'MultiLabel':
        merged = MultiLabel()
        for lbl in labels_list:
            merged.__encoded_labels |= lbl.getEncoded()
        return merged
    
__all__ = ['LabelsEnum','MultiLabel']
