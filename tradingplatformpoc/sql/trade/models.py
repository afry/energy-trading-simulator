import datetime

from pydantic.types import Optional

from sqlalchemy import Column, DateTime, Enum, Integer, cast, extract
from sqlalchemy.orm import column_property, declared_attr

from sqlmodel import Field, SQLModel

from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.market.trade import Market


class Trade(SQLModel, table=True):
    __tablename__ = 'trade'

    id: int = Field(
        title='Unique integer ID',
        sa_column=Column(Integer, autoincrement=True, primary_key=True, nullable=False)
    )
    job_id: str = Field(
        primary_key=False,
        default=None,
        title='Unique job ID',
        nullable=False
    )
    period: datetime.datetime = Field(
        title="Period",
        nullable=False,
        sa_column=Column(DateTime(timezone=True), primary_key=False)
    )
    action: Action = Field(
        title='Action',
        sa_column=Column(Enum(Action), primary_key=False, default=None, nullable=False)
    )
    resource: Resource = Field(
        title='Resource',
        sa_column=Column(Enum(Resource), primary_key=False, default=None, nullable=False)
    )
    quantity_pre_loss: float = Field(
        primary_key=False,
        default=None,
        title='Quantity pre loss',
        nullable=False
    )
    quantity_post_loss: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Quantity post loss',
        nullable=True
    )
    price: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Price',
        nullable=True
    )
    source: str = Field(
        primary_key=False,
        default=None,
        title='Source',
        nullable=False
    )
    by_external: bool = Field(
        primary_key=False,
        default=None,
        title='Trade by external market',
        nullable=False
    )
    market: Market = Field(
        title='Market',
        sa_column=Column(Enum(Market), primary_key=False, default=None, nullable=False)
    )
    tax_paid: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Tax paid',
        nullable=True
    )
    grid_fee_paid: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Grid fee paid',
        nullable=True
    )

    @declared_attr
    def tax_paid_for_quantity(self):
        return column_property(self.quantity_post_loss * self.tax_paid)
    
    @declared_attr
    def grid_fee_paid_for_quantity(self):
        return column_property(self.quantity_post_loss * self.grid_fee_paid)
    
    @declared_attr
    def bought_for(self):
        return column_property(self.quantity_pre_loss * self.price)
    
    @declared_attr
    def sold_for(self):
        return column_property(self.quantity_post_loss * self.price)

    @declared_attr
    def month(self):
        return column_property(cast(extract('month', self.period), Integer))
    
    @declared_attr
    def year(self):
        return column_property(cast(extract('year', self.period), Integer))
