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
        title='Created time, with tz',
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), primary_key=False, nullable=False)
    )
    agents_spec: Optional[Dict[str, str]] = Field(
        title="Agents names and ids",
        sa_column=Column(JSONB(none_as_null=True), primary_key=False, nullable=True)
    )
    area_info: Optional[dict] = Field(
        title="Area info parameters",
        sa_column=Column(JSONB(none_as_null=True), primary_key=False, nullable=True)
    )
    mock_data_constants: Optional[dict] = Field(
        title="Mock data constants",
        sa_column=Column(JSONB(none_as_null=True), primary_key=False, nullable=True)
    )


class ConfigCreate(SQLModel):
    id: str
    description: str
    agents_spec: Dict[str, str]
    area_info: Dict[str, Any]
    mock_data_constants: Dict[str, Any]
