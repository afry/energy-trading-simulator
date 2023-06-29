import datetime
from typing import Optional

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
        nullable=False
    )
    created_at: Optional[datetime.datetime] = Field(
        primary_key=False,
        title='Created time, with tz',
        nullable=False,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    agents: Optional[list] = Field(
        primary_key=False,
        title="Agents",
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


class ConfigCreate(SQLModel):
    id: str
    description: str
    agents: list
    area_info: dict
    mock_data_constants: dict
