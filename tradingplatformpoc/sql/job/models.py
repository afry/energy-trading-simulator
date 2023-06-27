import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, String, func

from sqlmodel import Field, SQLModel


class Job(SQLModel, table=True):
    __tablename__ = 'job'

    id: str = Field(
        title='Unique string ID',
        sa_column=Column(String, autoincrement=False, primary_key=True, nullable=False)
    )
    created_at: Optional[datetime.datetime] = Field(
        primary_key=False,
        title='Created time, with tz',
        nullable=False,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    init_time: Optional[datetime.datetime] = Field(
        primary_key=False,
        title="Timestamp of simulation initialization, with tz",
        nullable=True,
        sa_column=Column(DateTime(timezone=True))
    )
    end_time: Optional[datetime.datetime] = Field(
        primary_key=False,
        title="Timestamp of simulation end, with tz",
        nullable=True,
        sa_column=Column(DateTime(timezone=True))
    )
