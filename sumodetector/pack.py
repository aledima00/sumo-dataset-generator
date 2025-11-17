from dataclasses import dataclass as _dc, field as _field
import pandas as _pd
from typing import Literal as _Lit

@_dc
class VInfo:
    id: str
    stType: int
    width: float = 0.0
    length: float = 0.0
    
    def asPandas(self) -> _pd.DataFrame:
        return _pd.DataFrame([{
            "VehicleId": self.id,
            "width": self.width,
            "length": self.length,
            "stType": self.stType
        }]).astype({
            "VehicleId": "string",
            "width": "float32",
            "length": "float32",
            "stType": "uint8"
        })
    
@_dc
class PInfo:
    id: str
    stType: int
    
    def asPandas(self) -> _pd.DataFrame:
        return _pd.DataFrame([{
            "VehicleId": self.id,
            "stType": self.stType
        }]).astype({
            "VehicleId": "string",
            "stType": "uint8"
        })



@_dc
class VehicleData:
    id: str
    position: tuple[float,float] = _field(default_factory=lambda: (0.0,0.0))
    speed: float = 0.0
    angle: float = 0.0
    def asPandas(self) -> _pd.DataFrame:
        df = _pd.DataFrame([{
            "VehicleId": self.id,
            "X": self.position[0],
            "Y": self.position[1],
            "Speed": self.speed,
            "Angle": self.angle,
        }]).astype({
            "VehicleId": "string",
            "X": "float32",
            "Y": "float32",
            "Speed": "float32",
            "Angle": "float32"
        })
        return df


@_dc
class FrameData:
    id: int
    pedestrians:list[VehicleData] = _field(default_factory=list)
    vehicles:list[VehicleData] = _field(default_factory=list)
    def asPandas(self) -> _pd.DataFrame:
        peds_df = _pd.concat([pd.asPandas() for pd in self.pedestrians], ignore_index=True) if len(self.pedestrians) > 0 else _pd.DataFrame()
        vehs_df = _pd.concat([vd.asPandas() for vd in self.vehicles], ignore_index=True) if len(self.vehicles) > 0 else _pd.DataFrame()
        df = _pd.concat([peds_df, vehs_df], ignore_index=True)
        df["FrameId"] = self.id
        df["FrameId"] = df["FrameId"].astype("uint8")
        return df
    

@_dc
class PackData:
    id: int
    frames:list[FrameData] = _field(default_factory=list)
    def asPandas(self) -> _pd.DataFrame:
        df = _pd.concat([fd.asPandas() for fd in self.frames], ignore_index=True)
        df["PackId"] = self.id
        df["PackId"] = df["PackId"].astype("uint32")
        return df
    
__all__ = ['VehicleData', 'FrameData', 'PackData', 'VInfo', 'PInfo']