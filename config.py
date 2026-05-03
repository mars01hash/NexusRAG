"""
Configuration management for RAG AI Decision Assistant
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Provider Selection
    provider: str = "gemini"  # Options: "openai", "deepseek", or "gemini"
    
    # OpenAI Configuration
    openai_api_key: str = ""  # Set in .env file
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    openai_base_url: str = "https://api.openai.com/v1"
    
    # DeepSeek Configuration
    deepseek_api_key: str = ""  # Set in .env file
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    
    # Google Gemini Configuration
    gemini_api_key: str = ""  # Set in .env file
    gemini_model: str = "gemini-3-flash-preview"
    
    temperature: float = 0.0
    
    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_ssl: bool = False
    redis_decode_responses: bool = True
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # RAG Configuration
    chunk_size: int = 1000
    chunk_overlap: int = 100
    top_k_results: int = 3
    
    # Data Configuration
    data_dir: str = "knowledge_data"
    index_path: str = "data/faiss_index"
    
    # Auth
    jwt_secret: str = "change-me-in-production-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

# Ensure data directory exists
Path(settings.data_dir).mkdir(exist_ok=True)
