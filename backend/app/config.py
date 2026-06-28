from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./health_data.db"
    oura_personal_access_token: str = ""
    garmin_email: str = ""
    garmin_password: str = ""
    # Optional: path to a `garth` token store (oauth1_token.json + oauth2_token.json).
    # If credentials are absent (or fail), the Garmin client tries this path first.
    # Defaults to ~/.garminconnect — where `garth` caches tokens after a successful
    # interactive login. Lets the VPS run without keeping the password in env.
    garmin_token_store: str = "~/.garminconnect"
    hevy_api_key: str = ""
    apple_health_api_key: str = ""
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_file": ".env"}


settings = Settings()
