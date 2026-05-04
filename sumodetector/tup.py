from abc import ABC as _ABC, abstractmethod as  _abstractmethod
import traci as _traci

class TraciUpdater(_ABC):
    @_abstractmethod
    def jumpTo(self, sim_time:int):
        pass
    @_abstractmethod
    def update(self):
        pass

class SimpleTraciUpdater(TraciUpdater):
    def jumpTo(self, sim_time):
        _traci.simulationStep(sim_time)
    def update(self):
        _traci.simulationStep()
