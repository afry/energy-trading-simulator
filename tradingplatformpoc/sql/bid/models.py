import datetime

from pydantic.types import Optional

from sqlalchemy import Column, DateTime, Enum, Integer

from sqlmodel import Field, SQLModel

from tradingplatformpoc.market.bid import Action, Resource


class Bid(SQLModel, table=True):
    __tablename__ = 'bid'

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
    quantity: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Accepted quantity',
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
