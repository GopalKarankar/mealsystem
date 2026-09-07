from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path

class Settings(BaseSettings):
    debug: bool = True
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "meal_system"

    groq_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"

    nvidia_api_key: str
    nvidia_api_base_url: str = "https://integrate.api.nvidia.com/v1"

    nvidia_asr_function_id: str = ""
    nvidia_asr_grpc_uri: str = "grpc.nvcf.nvidia.com:443"
    nvidia_asr_language_code: str = "en-US"

    upload_dir: str = "temp_audio"
    max_audio_size_mb: int = 25

    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    google_client_id: str = ""
    google_client_secret: str = ""

    class Config:
        env_file = str(Path(__file__).resolve().parent.parent / ".env")

    @property
    def origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]

settings = Settings()
