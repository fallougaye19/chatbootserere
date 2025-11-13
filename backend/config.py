from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    database_url: str = "postgresql:///./serere_translation.db"
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    ai_model_url: Optional[str] = "https://dt95o23hh7k5zd-8000.proxy.runpod.net"
    
    class Config:
        env_file = ".env"


settings = Settings()
