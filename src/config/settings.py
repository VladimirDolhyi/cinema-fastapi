from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PATH_TO_DB: str = "sqlite:///./src/database/source/cinema.db"


settings = Settings()
