import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import BYTEA, JSONB

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
        title='Created time, with tz',
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), primary_key=False, nullable=False)
    )
    agent_id: str = Field(
        title="Agent ID",
        sa_column=Column(String, primary_key=False, nullable=False)
    )
    mock_data_constants: dict = Field(
        title="Mock data constants",
        sa_column=Column(JSONB(none_as_null=True), primary_key=False, nullable=False)
    )
    mock_data: Optional[bytes] = Field(
        title="Mock data for agent",
        sa_column=Column(BYTEA, primary_key=False, nullable=True)
    )
