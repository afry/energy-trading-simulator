from pydantic.types import Optional

from sqlalchemy import Column, Integer

from sqlmodel import Field, SQLModel


class HeatingPrice(SQLModel, table=True):
    __tablename__ = 'heating_price'

    id: Optional[int] = Field(
        title='Unique integer ID',
        sa_column=Column(Integer, autoincrement=True, primary_key=True, nullable=False)
    )
    job_id: Optional[str] = Field(
        primary_key=False,
        default=None,
        title='Unique job ID',
        nullable=False
    )
    year: Optional[int] = Field(
        primary_key=False,
        default=None,
        title="Year",
        nullable=True,
    )
    month: Optional[int] = Field(
        primary_key=False,
        default=None,
        title="Month",
        nullable=True,
    )
    estimated_retail_price: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Estimated retail price',
        nullable=False
    )
    estimated_wholesale_price: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Estimated wholesale price',
        nullable=False
    )
    exact_retail_price: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Exact retail price',
        nullable=False
    )
    exact_wholesale_price: Optional[float] = Field(
        primary_key=False,
        default=None,
        title='Exact wholesale price',
        nullable=False
    )
