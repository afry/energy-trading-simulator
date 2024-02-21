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
    SUM_IMPORT_ELEC = 'SUM_IMPORT_ELEC'
    SUM_EXPORT_ELEC = 'SUM_EXPORT_ELEC'
    SUM_NET_IMPORT_ELEC = 'Net electricity import [kWh]'
    MONTHLY_SUM_IMPORT_ELEC = 'MONTHLY_SUM_IMPORT_ELEC'
    MONTHLY_SUM_EXPORT_ELEC = 'MONTHLY_SUM_EXPORT_ELEC'
    MONTHLY_SUM_NET_IMPORT_ELEC = 'MONTHLY_SUM_NET_IMPORT_ELEC'
    MONTHLY_MAX_NET_IMPORT_ELEC = 'MONTHLY_MAX_NET_IMPORT_ELEC'
    SUM_IMPORT_HEAT = 'SUM_IMPORT_HEAT'
    SUM_EXPORT_HEAT = 'SUM_EXPORT_HEAT'
    SUM_NET_IMPORT_HEAT = 'Net heating import [kWh]'
    MONTHLY_SUM_IMPORT_HEAT = 'MONTHLY_SUM_IMPORT_HEAT'
    MONTHLY_SUM_EXPORT_HEAT = 'MONTHLY_SUM_EXPORT_HEAT'
    MONTHLY_SUM_NET_IMPORT_HEAT = 'MONTHLY_SUM_NET_IMPORT_HEAT'
    MONTHLY_MAX_NET_IMPORT_HEAT = 'MONTHLY_MAX_NET_IMPORT_HEAT'
    SUM_IMPORT_JAN_FEB_ELEC = 'SUM_IMPORT_JAN_FEB_ELEC'
    SUM_EXPORT_JAN_FEB_ELEC = 'SUM_EXPORT_JAN_FEB_ELEC'
    SUM_IMPORT_BELOW_1_C_ELEC = 'SUM_IMPORT_BELOW_1_C_ELEC'
    SUM_EXPORT_BELOW_1_C_ELEC = 'SUM_EXPORT_BELOW_1_C_ELEC'
    SUM_IMPORT_JAN_FEB_HEAT = 'Heating import Jan-Feb [kWh]'
    SUM_EXPORT_JAN_FEB_HEAT = 'SUM_EXPORT_JAN_FEB_HEAT'
    SUM_IMPORT_BELOW_1_C_HEAT = 'Heating import when <1C [kWh]'
    SUM_EXPORT_BELOW_1_C_HEAT = 'SUM_EXPORT_BELOW_1_C_HEAT'
    LOCALLY_PRODUCED_RESOURCES = 'Local prod. {} [kWh]'
