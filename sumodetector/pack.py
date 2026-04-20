from dataclasses import dataclass as _dc, field as _field
import pandas as _pd
import pyarrow as _pa

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
class Frame:
    vehicles:list[VehicleData] = _field(default_factory=list)
    def asPandas(self,id:int) -> _pd.DataFrame:
        vehs_df = _pd.concat([vd.asPandas() for vd in self.vehicles], ignore_index=True) if len(self.vehicles) > 0 else _pd.DataFrame()
        df = vehs_df
        if df.empty:
            return df
        df["FrameId"] = id
        df["FrameId"] = df["FrameId"].astype("uint8")
        return df

def PackSchema() -> _pa.schema:
    return _pa.schema([
            _pa.field("VehicleId", _pa.string()),
            _pa.field("X", _pa.float32()),
            _pa.field("Y", _pa.float32()),
            _pa.field("Speed", _pa.float32()),
            _pa.field("Angle", _pa.float32()),
            _pa.field("FrameId", _pa.uint8()),
            _pa.field("PackId", _pa.uint32()),
        ])


def pack2pandas(id:int, frames:list[Frame]) -> _pd.DataFrame:
    df = _pd.concat([fd.asPandas(i) for i,fd in enumerate(frames)], ignore_index=True)
    if df.empty:
        return None
    df["PackId"] = id
    df["PackId"] = df["PackId"].astype("uint32")
    return df
        
    
__all__ = ['VehicleData', 'Frame','PackSchema', 'pack2pandas', 'VInfo', 'PInfo']