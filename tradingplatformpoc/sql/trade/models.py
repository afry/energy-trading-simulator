import datetime

from pydantic.types import Optional

from sqlalchemy import Column, DateTime, Enum, Integer

from sqlmodel import Field, SQLModel

from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.market.trade import Market


class Trade(SQLModel, table=True):
    __tablename__ = 'trade'

    id: Optional[int] = Field(
        title='Unique integer ID',
        sa_column=Column(Integer, autoincrement=True, primary_key=True, nullable=False)
    )
    job_id: Optional[str] = Field(
        primary_key=False,
        default=None,
        title='Unique job ID',
        nullable=False
    )
    period: Optional[datetime.datetime] = Field(
        primary_key=False,
        title="Period",
        nullable=True,
        sa_column=Column(DateTime(timezone=True))
    )
    action: Optional[str] = Field(
        title='Action',
        sa_column=Column(Enum(Action), primary_key=False, default=None, nullable=False)
    )
    resource: Optional[str] = Field(
        title='Resource',
        sa_column=Column(Enum(Resource), primary_key=False, default=None, nullable=False)
    )
    quantity_pre_loss: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Quantity pre loss',
        nullable=False
    )
    quantity_post_loss: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Quantity post loss',
        nullable=False
    )
    price: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Price',
        nullable=False
    )
    source: Optional[str] = Field(
        primary_key=False,
        default=None,
        title='Source',
        nullable=False
    )
    by_external: Optional[bool] = Field(
        primary_key=False,
        default=None,
        title='Trade by external market',
        nullable=False
    )
    market: Optional[str] = Field(
        title='Market',
        sa_column=Column(Enum(Market), primary_key=False, default=None, nullable=False)
    )
    tax_paid: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Tax paid',
        nullable=False
    )
    grid_fee_paid: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Grid fee paid',
        nullable=False
    )
