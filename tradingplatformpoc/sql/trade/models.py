from pydantic.types import Optional

from sqlalchemy import Column, Integer

from sqlmodel import Field, SQLModel


class Trade(SQLModel, table=True):
    __tablename__ = 'trade'

    id: Optional[int] = Field(
        title='Unique integer ID',
        sa_column=Column(Integer, autoincrement=False, primary_key=True, nullable=False)
    )
