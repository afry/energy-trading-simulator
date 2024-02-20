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
    TAX_PAID = 'Tax paid [SEK]'
    GRID_FEES_PAID = 'Grid fees paid [SEK]'
    NET_ENERGY_SPEND = 'Net energy spend [SEK]'
    SUM_NET_IMPORT_ELEC = 'Net electricity import [kWh]'
    MONTHLY_SUM_NET_IMPORT_ELEC = 'MONTHLY_SUM_NET_IMPORT_ELEC'
    MONTHLY_MAX_NET_IMPORT_ELEC = 'MONTHLY_MAX_NET_IMPORT_ELEC'
    SUM_NET_IMPORT_HEAT = 'Net heating import [kWh]'
    MONTHLY_SUM_NET_IMPORT_HEAT = 'MONTHLY_SUM_NET_IMPORT_HEAT'
    MONTHLY_MAX_NET_IMPORT_HEAT = 'MONTHLY_MAX_NET_IMPORT_HEAT'
    LOCALLY_PRODUCED_ELECTRICITY = 'Local prod. electricity [kWh]'
    LOCALLY_PRODUCED_COOLING = 'Local prod. cooling [kWh]'
    LOCALLY_PRODUCED_HEATING = 'Local prod. heating [kWh]'
