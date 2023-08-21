import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB

from sqlmodel import Field, SQLModel

from tradingplatformpoc.sql.job.models import uuid_as_str_generator


class MockData(SQLModel, table=True):
    __tablename__ = 'mock_data'

    id: str = Field(
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
    agent_id: str = Field(
        primary_key=False,
        title="Agent ID",
        nullable=False,
        sa_column=Column(String)
    )
    mock_data_constants: dict = Field(
        primary_key=False,
        title="Mock data constants",
        nullable=False,
        sa_column=Column(JSONB(none_as_null=True))
    )
    # mock_data: Optional[bytearray] = Field(
    #     primary_key=False,
    #     title="Mock data for agent",
    #     nullable=True,
    #     sa_column=Column(bytearray)
    # )
