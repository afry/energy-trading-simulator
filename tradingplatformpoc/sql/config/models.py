import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB

from sqlmodel import Field, SQLModel


class Config(SQLModel, table=True):
    __tablename__ = 'config'

    id: str = Field(
        title='Unique string ID',
        sa_column=Column(String, autoincrement=False, primary_key=True, nullable=False)
    )
    description: Optional[str] = Field(
        primary_key=False,
        title='Description of configuration',
        nullable=True
    )
    created_at: Optional[datetime.datetime] = Field(
        primary_key=False,
        title='Created time, with tz',
        nullable=False,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    agents_spec: Optional[Dict[str, str]] = Field(
        primary_key=False,
        title="Agents names and ids",
        nullable=True,
        sa_column=Column(JSONB(none_as_null=True))
    )
    area_info: Optional[dict] = Field(
        primary_key=False,
        title="Area info parameters",
        nullable=True,
        sa_column=Column(JSONB(none_as_null=True))
    )
    mock_data_constants: Optional[dict] = Field(
        primary_key=False,
        title="Mock data constants",
        nullable=True,
        sa_column=Column(JSONB(none_as_null=True))
    )
    general: Optional[dict] = Field(
        primary_key=False,
        title="General settings",
        nullable=True,
        sa_column=Column(JSONB(none_as_null=True))
    )


class ConfigCreate(SQLModel):
    id: str
    description: str
    agents_spec: Dict[str, str]
    area_info: Dict[str, Any]
    mock_data_constants: Dict[str, Any]
    general: Dict[str, Any]
