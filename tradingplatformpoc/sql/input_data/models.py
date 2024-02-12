import datetime

from sqlalchemy import Column, DateTime

from sqlmodel import Field, SQLModel


class InputData(SQLModel, table=True):
    __tablename__ = 'input_data'

    period: datetime.datetime = Field(
        title="Period",
        sa_column=Column(DateTime(timezone=True), primary_key=True, nullable=False)
    )
    irradiation: float = Field(
        primary_key=False,
        default=None,
        title='Solar irradiation, according to SMHI, in Watt per square meter.',
        nullable=False
    )
    temperature: float = Field(
        primary_key=False,
        default=None,
        title='Outdoor temperature, degrees Celsius.',
        nullable=False
    )
    rad_energy: float = Field(
        primary_key=False,
        default=None,
        title='Radiator heating energy consumption, in kW.',
        nullable=False
    )
    hw_energy: float = Field(
        primary_key=False,
        default=None,
        title='Hot water heating energy consumption, in kW.',
        nullable=False
    )
    coop_electricity_consumed: float = Field(
        primary_key=False,
        default=None,
        title='Coop electricity consumed (cooling and other), in kWh.',
        nullable=False
    )
    coop_hot_tap_water_consumed: float = Field(
        primary_key=False,
        default=None,
        title='Coop hot tap water consumed, in kWh.',
        nullable=False
    )
    coop_space_heating_consumed: float = Field(
        primary_key=False,
        default=None,
        title='Coop space heating consumed (net), in kWh.',
        nullable=False
    )
