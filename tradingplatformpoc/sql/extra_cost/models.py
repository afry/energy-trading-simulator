import datetime

from pydantic.types import Optional

from sqlalchemy import Column, DateTime, Integer

from sqlmodel import Field, SQLModel


class ExtraCost(SQLModel, table=True):
    __tablename__ = 'extra_cost'

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
    agent: Optional[str] = Field(
        primary_key=False,
        default=None,
        title='Agent',
        nullable=False
    )
    type: Optional[str] = Field(
        primary_key=False,
        default=None,
        title='Type',
        nullable=False
    )
    cost: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Level',
        nullable=False
    )
