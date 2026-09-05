import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Project SENTINEL"
    API_V1_STR: str = "/api/v1"
    
    # PostgreSQL + PostGIS credentials
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "sentinel_admin")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "sentinel_secret")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "sentinel_db")
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    
    # Synchronous DB URL (for migrations, initialization & PostGIS queries)
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            return url
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        
    # Asynchronous DB URL (for high-concurrency FastAPI asyncpg)
    @property
    def ASYNC_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        
    # Redis Cache & Watchlist (supports cloud Upstash or local)
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)
    
    # MediaMTX Streaming Server
    MEDIAMTX_HOST: str = os.getenv("MEDIAMTX_HOST", "localhost")
    MEDIAMTX_API_PORT: int = int(os.getenv("MEDIAMTX_API_PORT", "9997"))
    MEDIAMTX_RTSP_PORT: int = int(os.getenv("MEDIAMTX_RTSP_PORT", "8554"))
    MEDIAMTX_HLS_PORT: int = int(os.getenv("MEDIAMTX_HLS_PORT", "8888"))
    
    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
