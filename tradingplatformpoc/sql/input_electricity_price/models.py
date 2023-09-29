import datetime

from sqlalchemy import Column, DateTime

from sqlmodel import Field, SQLModel


class InputElectricityPrice(SQLModel, table=True):
    __tablename__ = 'input_electricity_price'

    period: datetime.datetime = Field(
        title="Period",
        sa_column=Column(DateTime(timezone=True), primary_key=True, nullable=False)
    )
    dayahead_se3_el_price: float = Field(
        primary_key=False,
        default=None,
        title='Nordpool day ahead electricity price for SE3, in SEK.',
        nullable=False
    )
