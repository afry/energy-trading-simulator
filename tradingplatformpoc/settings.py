import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from pydantic import BaseSettings


logger = logging.getLogger(__name__)


dotenv_path = Path('.env')
load_dotenv(dotenv_path=dotenv_path)


def check_envvar_is_not_none(envvar):
    if envvar is not None:
        return envvar
    else:
        logger.error('Missing required environment variable, setting value to None.')
        raise TypeError('Required environment variable is None, should be string.')


class Settings(BaseSettings):
    DB_USER: str = check_envvar_is_not_none(os.getenv('PG_USER'))
    DB_PASSWORD: str = check_envvar_is_not_none(os.getenv('PG_PASSWORD'))
    DB_HOST: str = check_envvar_is_not_none(os.getenv('PG_HOST'))
    DB_DATABASE: str = check_envvar_is_not_none(os.getenv('PG_DATABASE'))
    DB_DATABASE_TEST: Optional[str] = os.getenv('PG_DATABASE_TEST')


settings = Settings()