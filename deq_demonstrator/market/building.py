from local_energy_market.classes import Building
from deq_demonstrator.market.market_agent import MarketAgentFiware
from deq_demonstrator.data_models import Device
from deq_demonstrator.settings import settings

class BuildingFiware(Building, Device):
    def __init__(self, building_id: int, nodes: dict, *args, **kwargs):
        Building.__init__(self, building_id=building_id, nodes=nodes, *args, **kwargs)
        Device.__init__(self,*args, **kwargs)

        self.market_agent = MarketAgentFiware(agent_id=building_id, building=self, *args, **kwargs)

    def run(self):
        self.market_agent.run()
