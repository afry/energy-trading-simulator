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
