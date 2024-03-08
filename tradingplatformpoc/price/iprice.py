
import datetime
from abc import ABC, abstractmethod

from tradingplatformpoc.market.bid import Resource


class IPrice(ABC):
    resource: Resource
    transfer_loss_per_side: float
    wholesale_offset: float
    tax: float  # SEK/kWh
    grid_fee: float  # SEK/kWh

    def __init__(self, resource: Resource):
        self.resource = resource
        self.wholesale_offset = 0
        self.tax = 0
        self.grid_fee = 0

    @abstractmethod
    def get_estimated_retail_price(self, period: datetime.datetime, include_tax: bool) -> float:
        """
        Returns the price at which the external grid operator is believed to be willing to sell energy, in SEK/kWh.
        For some energy carriers the price may be known, but for others it may in fact be set after the fact. That is
        why this method is named 'estimated'.
        """
        pass

    @abstractmethod
    def get_estimated_wholesale_price(self, period: datetime.datetime) -> float:
        """
        Returns the price at which the external grid operator is believed to be willing to buy energy, in SEK/kWh.
        For some energy carriers the price may be known, but for others it may in fact be set after the fact. That is
        why this method is named 'estimated'.
        """
        pass

    @abstractmethod
    def get_exact_retail_price(self, period: datetime.datetime, include_tax: bool) -> float:
        """Returns the price at which the external grid operator is willing to sell energy, in SEK/kWh"""
        pass

    @abstractmethod
    def get_exact_wholesale_price(self, period: datetime.datetime) -> float:
        """Returns the price at which the external grid operator is willing to buy energy, in SEK/kWh"""
        pass

    def get_external_grid_buy_price(self, period: datetime.datetime):
        wholesale_price = self.get_estimated_wholesale_price(period)

        # Per https://doc.afdrift.se/pages/viewpage.action?pageId=17072325, Varberg Energi can pay an extra
        # remuneration on top of the Nordpool spot price. This can vary, "depending on for example membership".
        # Might make sense to make this number configurable.
        remuneration_modifier = 0

        return wholesale_price + remuneration_modifier
