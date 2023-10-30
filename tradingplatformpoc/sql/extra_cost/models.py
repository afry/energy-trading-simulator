import datetime

from pydantic.types import Optional

from sqlalchemy import Column, DateTime, Enum, Integer

from sqlmodel import Field, SQLModel

from tradingplatformpoc.market.extra_cost import ExtraCostType


class ExtraCost(SQLModel, table=True):
    __tablename__ = 'extra_cost'

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
        nullable=True,
        sa_column=Column(DateTime(timezone=True), primary_key=False)
    )
    agent: str = Field(
        primary_key=False,
        default=None,
        title='Agent',
        nullable=False
    )
    cost_type: str = Field(
        title='Cost type',
        sa_column=Column(Enum(ExtraCostType), primary_key=False, default=None, nullable=False)
    )
    cost: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Level',
        nullable=True
    )
