import datetime

from pydantic.types import Optional

from sqlalchemy import Column, DateTime, Integer

from sqlmodel import Field, SQLModel


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
        title="Timestamps for user viewing nudge cards",
        nullable=True,
        sa_column=Column(DateTime(timezone=True))
    )
    action: Optional[str] = Field(
        primary_key=False,
        default=None,
        title='Action',
        nullable=False
    )
    resource: Optional[str] = Field(
        primary_key=False,
        default=None,
        title='Resource',
        nullable=False
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
        primary_key=False,
        default=None,
        title='Market',
        nullable=False
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
