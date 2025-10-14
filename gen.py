from os import path
from pygenerator.graph import Graph
from pygenerator.vehicles import VClass, VParams, IParams
from pygenerator.generator import Generator

# map params
nodes_raw = ("nw","ne","se","sw")
edges_raw = [
    ("ne", "nw"),
    ("nw", "sw"),
    ("sw", "se"),
    ("se", "ne"),
    ("se", "sw"),
    ("sw", "nw"),
    ("nw", "ne"),
    ("ne", "se")
]
G = Graph(nodes_raw=nodes_raw,edges_raw=edges_raw)

# file params
OUTPUT_FILE = path.join(path.dirname(__file__),"generated","roundabout","cars.rou.xml")
TIME_HORIZON_S = 200  # seconds

# route generation params
N_ROUTES = 10
MIN_RTLEN = 3
MAX_RTLEN = 6

# vehicle generation params
VNUM = 50
TDEV_PROP = 0.1

ip_probabs = {
    "NORMAL": (0.5,IParams(speed_factor=1.0, speed_dev=0.1, min_gap_m=2.5)),
    "CAUTIOUS": (0.2,IParams(speed_factor=0.8, speed_dev=0.05, min_gap_m=3.5)),
    "AGGRESSIVE": (0.2,IParams(speed_factor=1.2, speed_dev=0.15, min_gap_m=2.0)),
    "RECKLESS": (0.05,IParams(speed_factor=1.5, speed_dev=0.2, min_gap_m=1.5)),
    "AUTHORIZED": (0.05,IParams(speed_factor=2.0, speed_dev=0.25, min_gap_m=0.5))
}

vp_probabs = {
    "CAR" : (0.55,VParams(accel=2.6, decel=4.5, emergency_decel=9.0, length_m=5.0, max_speed_kmh=180.0)),
    "RACECAR" : (0.02,VParams(accel=4.0, decel=8.0, emergency_decel=13.0, length_m=4.5, max_speed_kmh=300.0)),
    "TRUCK" : (0.07,VParams(accel=1.2, decel=3.5, emergency_decel=7.0, length_m=12.0, max_speed_kmh=120.0)),
    "BUS" : (0.07,VParams(accel=1.5, decel=3.0, emergency_decel=8.0, length_m=10.0, max_speed_kmh=130.0)),
    "MOTORCYCLE" : (0.29,VParams(accel=3.5, decel=5.0, emergency_decel=10.0, length_m=2.5, max_speed_kmh=220.0))
}

vcl_params = {
    "PASSENGER": (0.95,VClass.PASSENGER.value),
    "EMERGENCY": (0.02,VClass.EMERGENCY.value),
    "AUTHORITY": (0.02,VClass.AUTHORITY.value),
    "ARMY": (0.01,VClass.ARMY.value)
}

probabilistic_mod_multipliers={
    "DAMAGED_BRAKES": {"p":0.04, "modifications":{"decel":0.7, "emergency_decel":0.3}},
    "FLAT_TIRE": {"p":0.07, "modifications":{"max_speed_kmh":0.7}},
    "HEAVY_LOAD": {"p":0.1, "modifications":{"accel":0.8, "max_speed_kmh":0.9}},
    "DISTRACTED_DRIVER": {"p":0.1, "modifications":{"speed_factor":0.9, "speed_dev":1.5, "min_gap_m":0.5, "emergency_decel":0.8}}
}

def main():
    generator = Generator(
        OUTPUT_FILE=OUTPUT_FILE,
        TIME_HORIZON_S=TIME_HORIZON_S,
        N_ROUTES=N_ROUTES,
        MIN_RTLEN=MIN_RTLEN,
        MAX_RTLEN=MAX_RTLEN,
        VNUM=VNUM,
        TDEV_PROP=TDEV_PROP,
        ip_probabs=ip_probabs,
        vp_probabs=vp_probabs,
        vcl_params=vcl_params,
        graph=G,
        probabilistic_mod_multipliers=probabilistic_mod_multipliers,
        source_nodes=[G.NCL(n) for n in ("cwsn","ccwsn")]
    )

    generator.generate()

if __name__ == "__main__":
    main()
