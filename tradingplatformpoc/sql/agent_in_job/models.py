import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, func

from sqlmodel import Field, SQLModel


class AgentInJob(SQLModel, table=True):
    __tablename__ = 'agents_in_job'

    id: int = Field(
        title='Unique integer ID',
        sa_column=Column(Integer, autoincrement=True, primary_key=True, nullable=False)
    )
    created_at: Optional[datetime.datetime] = Field(
        primary_key=False,
        title='Created time, with tz',
        nullable=False,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    agent_id: Optional[str] = Field(
        primary_key=False,
        title="Agent ID",
        nullable=True,
        sa_column=Column(String)
    )
    job_id: Optional[str] = Field(
        primary_key=False,
        title="Agent ID",
        nullable=True,
        sa_column=Column(String)
    )
