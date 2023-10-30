import datetime

from pydantic.types import Optional

from sqlalchemy import Column, DateTime, Enum, Integer

from sqlmodel import Field, SQLModel

from tradingplatformpoc.market.bid import Action, Resource


class Bid(SQLModel, table=True):
    __tablename__ = 'bid'

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
    quantity: float = Field(
        primary_key=False,
        default=None,
        title='Accepted quantity',
        nullable=False
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
