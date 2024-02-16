from typing import Any, Dict

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from sqlmodel import Field, SQLModel


class PreCalculatedResults(SQLModel, table=True):
    __tablename__ = 'results'

    job_id: str = Field(
        primary_key=True,
        title='Job ID',
        nullable=False
    )
    result_dict: Dict[str, Any] = Field(
        title="Results dict",
        sa_column=Column(JSONB(none_as_null=True), primary_key=False, nullable=False)
    )


class ResultsKey:
    TAX_PAID = 'TAX_PAID'
    GRID_FEES_PAID = 'GRID_FEES_PAID'
    SUM_NET_IMPORT = 'SUM_NET_IMPORT'
    MONTHLY_SUM_NET_IMPORT = 'MONTHLY_SUM_NET_IMPORT'
    MONTHLY_MAX_NET_IMPORT = 'MONTHLY_MAX_NET_IMPORT'
    SUM_LEC_EXPENDITURE = 'SUM_LEC_EXPENDITURE'
