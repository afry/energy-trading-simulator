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
    SUM_IMPORT = '{} import [kWh]'
    SUM_EXPORT = '{} export [kWh]'
    SUM_NET_IMPORT = 'Net {} import [kWh]'
    MONTHLY_SUM_IMPORT_ELEC = 'MONTHLY_SUM_IMPORT_ELEC'
    MONTHLY_SUM_EXPORT_ELEC = 'MONTHLY_SUM_EXPORT_ELEC'
    MONTHLY_SUM_NET_IMPORT_ELEC = 'MONTHLY_SUM_NET_IMPORT_ELEC'
    MONTHLY_MAX_NET_IMPORT_ELEC = 'MONTHLY_MAX_NET_IMPORT_ELEC'
    MONTHLY_SUM_IMPORT_HEAT = 'MONTHLY_SUM_IMPORT_HEAT'
    MONTHLY_SUM_EXPORT_HEAT = 'MONTHLY_SUM_EXPORT_HEAT'
    MONTHLY_SUM_NET_IMPORT_HEAT = 'MONTHLY_SUM_NET_IMPORT_HEAT'
    MONTHLY_MAX_NET_IMPORT_HEAT = 'MONTHLY_MAX_NET_IMPORT_HEAT'
    SUM_IMPORT_JAN_FEB = '{} import Jan-Feb [kWh]'
    SUM_EXPORT_JAN_FEB = '{} export Jan-Feb [kWh]'
    SUM_IMPORT_BELOW_1_C = '{} import when <1C [kWh]'
    SUM_EXPORT_BELOW_1_C = '{} export when <1C [kWh]'
    LOCALLY_PRODUCED_RESOURCES = 'Local prod. {} [kWh]'

    @staticmethod
    def format_results_key_name(results_key_name: str, to_insert: str) -> str:
        """
        For example, the following inputs:
        results_key_name = '{} import when <1C [kWh]'
        resource = Resource.HEATING
        should lead to the following output:
        'Heating import when <1C [kWh]'
        """
        new_name = results_key_name.format(to_insert.lower())
        return new_name[0].upper() + new_name[1:]