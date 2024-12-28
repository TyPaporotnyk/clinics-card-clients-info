from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    CLINICS_CARD_API_KEY: str

    GOOGLE_SPREADSHEET_KEY: str
    GOOGLE_WORKSHEET_NAME: str


settings = Settings()
