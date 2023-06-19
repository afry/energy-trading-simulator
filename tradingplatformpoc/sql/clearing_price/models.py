import datetime

from pydantic.types import Optional

from sqlalchemy import Column, DateTime, Integer

from sqlmodel import Field, SQLModel


class ClearingPrice(SQLModel, table=True):
    __tablename__ = 'clearing_price'

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
    resource: Optional[str] = Field(
        primary_key=False,
        default=None,
        title='Resource',
        nullable=False
    )
    price: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Price',
        nullable=False
    )
