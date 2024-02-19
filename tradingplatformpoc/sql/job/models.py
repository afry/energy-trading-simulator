import datetime
import uuid
from typing import Optional

from sqlalchemy import Column, DateTime, func

from sqlmodel import Field, SQLModel


def uuid_as_str_generator() -> str:
    return str(uuid.uuid4())


class Job(SQLModel, table=True):
    __tablename__ = 'job'

    id: str = Field(
        default_factory=uuid_as_str_generator,
        primary_key=True,
        title='Unique ID',
        nullable=False
    )
    created_at: Optional[datetime.datetime] = Field(
        title='Created time, with tz',
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), primary_key=False, nullable=False)
    )
    start_time: Optional[datetime.datetime] = Field(
        title="Timestamp of simulation initialization, with tz",
        sa_column=Column(DateTime(timezone=True), primary_key=False, nullable=True)
    )
    end_time: Optional[datetime.datetime] = Field(
        title="Timestamp of simulation end, with tz",
        sa_column=Column(DateTime(timezone=True), primary_key=False, nullable=True)
    )
    config_id: str = Field(
        primary_key=False,
        title='Configuration ID',
        nullable=False
    )


class JobCreate(SQLModel):
    config_id: str
