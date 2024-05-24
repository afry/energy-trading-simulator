import datetime

from pydantic.types import Optional

from sqlalchemy import Column, DateTime, Integer

from sqlmodel import Field, SQLModel


class HeatingPrice(SQLModel, table=True):
    __tablename__ = 'heating_price'

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
    agent: str = Field(
        primary_key=False,
        default=None,
        title="Agent ID",
        nullable=True,
    )
    period: datetime.datetime = Field(
        title="Period",
        sa_column=Column(DateTime(timezone=True), primary_key=False, nullable=False)
    )
    estimated_retail_price: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Estimated retail price',
        nullable=True
    )
    estimated_wholesale_price: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Estimated wholesale price',
        nullable=True
    )
    exact_retail_price: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Exact retail price',
        nullable=True
    )
    exact_wholesale_price: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Exact wholesale price',
        nullable=True
    )
