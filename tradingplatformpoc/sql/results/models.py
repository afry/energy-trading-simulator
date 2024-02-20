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
    SUM_LEC_EXPENDITURE = 'SUM_LEC_EXPENDITURE'
    SUM_NET_IMPORT_ELEC = 'SUM_NET_IMPORT_ELEC'
    MONTHLY_SUM_NET_IMPORT_ELEC = 'MONTHLY_SUM_NET_IMPORT_ELEC'
    MONTHLY_MAX_NET_IMPORT_ELEC = 'MONTHLY_MAX_NET_IMPORT_ELEC'
    SUM_NET_IMPORT_HEAT = 'SUM_NET_IMPORT_HEAT'
    MONTHLY_SUM_NET_IMPORT_HEAT = 'MONTHLY_SUM_NET_IMPORT_HEAT'
    MONTHLY_MAX_NET_IMPORT_HEAT = 'MONTHLY_MAX_NET_IMPORT_HEAT'
    LOCALLY_PRODUCED_ELECTRICITY = 'LOCALLY_PRODUCED_ELECTRICITY'
    LOCALLY_PRODUCED_COOLING = 'LOCALLY_PRODUCED_COOLING'
    LOCALLY_PRODUCED_HEATING = 'LOCALLY_PRODUCED_HEATING'
