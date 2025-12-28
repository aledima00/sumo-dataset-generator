import sumodetector.console as sumoDetConsole
from sumodetector.labels import LabelsEnum as _LE

if __name__ == "__main__":
    sumoDetConsole.setActiveLabels( {_LE.EMERGENCY_BRAKING} )
    sumoDetConsole.runSimulation()