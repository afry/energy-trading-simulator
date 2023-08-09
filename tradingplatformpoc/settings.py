import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from pydantic import BaseSettings

dotenv_path = Path('.env')
load_dotenv(dotenv_path=dotenv_path)


class Settings(BaseSettings):
    DB_USER: Optional[str] = os.getenv('PG_USER')
    DB_PASSWORD: Optional[str] = os.getenv('PG_PASSWORD')
    DB_HOST: Optional[str] = os.getenv('PG_HOST')
    DB_DATABASE: Optional[str] = os.getenv('PG_DATABASE')
    DB_DATABASE_TEST: Optional[str] = os.getenv('PG_DATABASE_TEST')


settings = Settings()
