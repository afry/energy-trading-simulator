import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB

from sqlmodel import Field, SQLModel

from tradingplatformpoc.sql.job.models import uuid_as_str_generator


class Agent(SQLModel, table=True):
    __tablename__ = 'agent'

    id: str = Field(
        default_factory=uuid_as_str_generator,
        primary_key=True,
        title='Unique ID',
        nullable=False
    )
    created_at: Optional[datetime.datetime] = Field(
        title='Created time, with tz',
        nullable=False,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), primary_key=False)
    )
    agent_type: str = Field(
        title='Agent type',
        nullable=False,
        sa_column=Column(String(50), primary_key=False)
    )
    agent_config: Dict[str, Any] = Field(
        title="Agent",
        nullable=False,
        sa_column=Column(JSONB(none_as_null=True), primary_key=False)
    )

    # TODO: Have a declared attribute that returns {'Type': self.agent_type, **self.agent_config}


class AgentCreate(SQLModel):
    agent_type: str
    agent_config: Dict[str, Any]
