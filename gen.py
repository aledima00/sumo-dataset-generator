from genrouter import IParams, VParams, VClass, getConsole
import colorama
colorama.init(autoreset=True)

# ==================== GENERATOR PROBABILITY DICTIONARIES ====================

ip_probabs = {
    "NORMAL": (0.5,IParams(speedFactor=1.0, speedDev=0.1, minGap=2.5)),
    "CAUTIOUS": (0.2,IParams(speedFactor=0.8, speedDev=0.05, minGap=3.5)),
    "AGGRESSIVE": (0.2,IParams(speedFactor=1.2, speedDev=0.15, minGap=2.0)),
    "RECKLESS": (0.05,IParams(speedFactor=1.5, speedDev=0.2, minGap=1.5)),
    "AUTHORIZED": (0.05,IParams(speedFactor=2.0, speedDev=0.25, minGap=0.5))
}

vp_probabs = {
    "CAR" : (0.55,VParams(accel=2.6, decel=4.5, emergency_decel=9.0, length_m=5.0, max_speed=180.0, gui_shape="passenger")),
    "RACECAR" : (0.02,VParams(accel=4.0, decel=8.0, emergency_decel=13.0, length_m=4.5, max_speed=300.0, gui_shape="passenger/sedan")),
    "TRUCK" : (0.07,VParams(accel=1.2, decel=3.5, emergency_decel=7.0, length_m=12.0, max_speed=120.0, gui_shape="truck")),
    "BUS" : (0.07,VParams(accel=1.5, decel=3.0, emergency_decel=8.0, length_m=10.0, max_speed=130.0, gui_shape="bus")),
    "MOTORCYCLE" : (0.29,VParams(accel=3.5, decel=5.0, emergency_decel=10.0, length_m=2.5, max_speed=220.0, gui_shape="motorcycle"))
}

vcl_params = {
    "PASSENGER": (0.95,VClass.PASSENGER.value),
    "EMERGENCY": (0.02,VClass.EMERGENCY.value),
    "AUTHORITY": (0.02,VClass.AUTHORITY.value),
    "ARMY": (0.01,VClass.ARMY.value)
}

probabilistic_mod_multipliers={
    "DAMAGED_BRAKES": {"p":0.2, "modifications":{"decel":0.4, "emergency_decel":0.2}},
    "FLAT_TIRE": {"p":0.07, "modifications":{"max_speed":0.7}},
    "HEAVY_LOAD": {"p":0.1, "modifications":{"accel":0.8, "max_speed":0.9}},
    "DISTRACTED_DRIVER": {"p":0.1, "modifications":{"speedFactor":0.9, "speedDev":1.5, "minGap":0.5, "emergency_decel":0.8}}
}


def main():
    console = getConsole(ip_probabs,vp_probabs,vcl_params,probabilistic_mod_multipliers)
    try:
        console()
    except Exception as e:
        print(f"{e}")

if __name__ == "__main__":
    main()