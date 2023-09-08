import datetime

from pydantic.types import Optional

from sqlalchemy import Column, DateTime, Integer

from sqlmodel import Field, SQLModel


class Level(SQLModel, table=True):
    __tablename__ = 'level'

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
        nullable=True,
        sa_column=Column(DateTime(timezone=True))
    )
    agent: str = Field(
        primary_key=False,
        default=None,
        title='Agent',
        nullable=False
    )
    type: str = Field(
        primary_key=False,
        default=None,
        title='Type',
        nullable=False
    )
    level: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Level',
        nullable=True
    )
