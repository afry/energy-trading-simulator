import datetime
import uuid
from typing import Optional

from sqlalchemy import Column, DateTime, func

from sqlmodel import Field, SQLModel


def uuid_as_str_generator() -> str:
    return str(uuid.uuid4())


class Job(SQLModel, table=True):
    __tablename__ = 'job'

    id: Optional[str] = Field(
        default_factory=uuid_as_str_generator,
        primary_key=True,
        title='Unique ID',
        nullable=False
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
    config_id: Optional[str] = Field(
        primary_key=False,
        title='Configuration ID',
        nullable=False
    )


class JobCreate(SQLModel):
    init_time: datetime.datetime
    config_id: str

    
class JobUpdate(SQLModel):
    end_time: datetime.datetime
