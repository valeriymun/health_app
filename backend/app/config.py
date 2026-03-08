from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./health_data.db"
    oura_personal_access_token: str = ""
    garmin_email: str = ""
    garmin_password: str = ""
    apple_health_api_key: str = ""
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_file": ".env"}


settings = Settings()
