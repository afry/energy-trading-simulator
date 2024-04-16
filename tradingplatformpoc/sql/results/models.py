from typing import Any, Dict

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from sqlmodel import Field, SQLModel

from tradingplatformpoc.market.trade import Resource


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
    MAX_NET_IMPORT = '{} peak import [kW]'
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
    HEAT_DUMPED = 'Heat dumped [kWh]'
    COOL_DUMPED = 'Cooling dumped [kWh]'

    @staticmethod
    def format_results_key_name(results_key_name: str, resource: Resource) -> str:
        """
        For example, the following inputs:
        results_key_name = '{} import when <1C [kWh]'
        resource = Resource.HIGH_TEMP_HEAT
        should lead to the following output:
        'High-temp heating import when <1C [kWh]'
        """
        new_name = results_key_name.format(resource.get_display_name())
        # .capitalize() makes the first character upper-case, but all others lower-case. Here, we make the first
        # character upper-case, but leave the others un-changed.
        return new_name[0].upper() + new_name[1:]
