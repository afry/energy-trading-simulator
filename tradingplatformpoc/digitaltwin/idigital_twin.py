from abc import ABC, abstractmethod

from ..bid import Resource


class IDigitalTwin(ABC):

    @abstractmethod
    def get_production(self, period, resource: Resource):
        # Return actual resource supplied for the trading horizon and energy carrier
        pass

    @abstractmethod
    def get_consumption(self, period, resource: Resource):
        # Return actual resource need for the trading horizon and energy carrier
        pass
