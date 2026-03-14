from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Mono Backend"
    app_version: str = "2.0"
    debug: bool = False
    allowed_origins: list = ["*"]

    model_config = {"env_file": ".env"}

settings = Settings()