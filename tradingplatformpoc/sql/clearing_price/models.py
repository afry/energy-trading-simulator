import datetime

from pydantic.types import Optional

from sqlalchemy import Column, DateTime, Enum, Integer

from sqlmodel import Field, SQLModel

from tradingplatformpoc.market.bid import Resource


class ClearingPrice(SQLModel, table=True):
    __tablename__ = 'clearing_price'

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
        primary_key=False,
        title="Period",
        nullable=False,
        sa_column=Column(DateTime(timezone=True))
    )
    resource: Resource = Field(
        title='Resource',
        sa_column=Column(Enum(Resource), primary_key=False, default=None, nullable=False)
    )
    price: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Price',
        nullable=True
    )