"""
Configuration module for JARVIS AI System.
Loads all environment variables and validates them at startup using Pydantic BaseSettings.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class AzureOpenAIConfig(BaseSettings):
    """Azure OpenAI configuration."""
    endpoint: str = Field(default="", alias="AZURE_OPENAI_ENDPOINT")
    api_key: str = Field(default="", alias="AZURE_OPENAI_API_KEY")
    api_version: str = Field(default="2024-06-01", alias="AZURE_OPENAI_API_VERSION")
    chat_deployment: str = Field(default="gpt-4o", alias="AZURE_OPENAI_CHAT_DEPLOYMENT")
    embedding_deployment: str = Field(default="text-embedding-3-small", alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    embedding_dimensions: int = Field(default=1536, alias="AZURE_OPENAI_EMBEDDING_DIMENSIONS")

    class Config:
        env_file = ".env"
        extra = "ignore"


class AzureSearchConfig(BaseSettings):
    """Azure AI Search configuration."""
    endpoint: str = Field(default="", alias="AZURE_SEARCH_ENDPOINT")
    api_key: str = Field(default="", alias="AZURE_SEARCH_API_KEY")
    index_name: str = Field(default="knowledge-index", alias="AZURE_SEARCH_INDEX_NAME")

    class Config:
        env_file = ".env"
        extra = "ignore"


class AzureBlobConfig(BaseSettings):
    """Azure Blob Storage configuration."""
    connection_string: str = Field(default="", alias="AZURE_BLOB_CONNECTION_STRING")
    container_name: str = Field(default="documents", alias="AZURE_BLOB_CONTAINER_NAME")

    class Config:
        env_file = ".env"
        extra = "ignore"


class AzureDocIntelligenceConfig(BaseSettings):
    """Azure Document Intelligence configuration."""
    endpoint: str = Field(default="", alias="AZURE_DOC_INTELLIGENCE_ENDPOINT")
    api_key: str = Field(default="", alias="AZURE_DOC_INTELLIGENCE_API_KEY")

    class Config:
        env_file = ".env"
        extra = "ignore"


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    database_url: str = Field(
        default="sqlite+aiosqlite:///jarvis.db",
        alias="DATABASE_URL"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"


class WhapiConfig(BaseSettings):
    """Whapi (WhatsApp API) configuration."""
    token: str = Field(default="", alias="WHAPI_TOKEN")
    base_url: str = Field(default="https://gate.whapi.cloud/messages/text", alias="WHAPI_BASE_URL")
    default_country_code: str = Field(default="91", alias="WHAPI_DEFAULT_COUNTRY_CODE")
    timeout_seconds: int = Field(default=30, alias="WHAPI_TIMEOUT_SECONDS")
    max_retries: int = Field(default=2, alias="WHAPI_MAX_RETRIES")

    class Config:
        env_file = ".env"
        extra = "ignore"


class TwilioConfig(BaseSettings):
    """Twilio SMS configuration."""
    account_sid: str = Field(default="", alias="TWILIO_ACCOUNT_SID")
    auth_token: str = Field(default="", alias="TWILIO_AUTH_TOKEN")
    from_number: str = Field(default="", alias="TWILIO_FROM_NUMBER")
    messaging_service_sid: str = Field(default="", alias="TWILIO_MESSAGING_SERVICE_SID")
    default_country_code: str = Field(default="91", alias="TWILIO_DEFAULT_COUNTRY_CODE")
    simulate: bool = Field(default=False, alias="TWILIO_SIMULATE")

    class Config:
        env_file = ".env"
        extra = "ignore"


class AppConfig(BaseSettings):
    """Application-level configuration."""
    app_name: str = Field(default="JARVIS AI System", alias="APP_NAME")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    secret_key: str = Field(default="change-me-in-production", alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiry_minutes: int = Field(default=60, alias="JWT_EXPIRY_MINUTES")
    max_input_length: int = Field(default=4000, alias="MAX_INPUT_LENGTH")
    max_file_size_mb: int = Field(default=50, alias="MAX_FILE_SIZE_MB")
    chunk_size: int = Field(default=500, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=100, alias="CHUNK_OVERLAP")
    top_k_results: int = Field(default=7, alias="TOP_K_RESULTS")
    appinsights_connection_string: str = Field(default="", alias="APPLICATIONINSIGHTS_CONNECTION_STRING")

    class Config:
        env_file = ".env"
        extra = "ignore"


class Settings:
    """Master settings container that aggregates all configuration sections."""

    def __init__(self):
        self.app = AppConfig()
        self.azure_openai = AzureOpenAIConfig()
        self.azure_search = AzureSearchConfig()
        self.azure_blob = AzureBlobConfig()
        self.azure_doc_intelligence = AzureDocIntelligenceConfig()
        self.database = DatabaseConfig()
        self.whapi = WhapiConfig()
        self.twilio = TwilioConfig()

    def validate_azure_services(self) -> dict:
        """Check which Azure services are configured and return status."""
        status = {
            "azure_openai": bool(self.azure_openai.endpoint and self.azure_openai.api_key),
            "azure_search": bool(self.azure_search.endpoint and self.azure_search.api_key),
            "azure_blob": bool(self.azure_blob.connection_string),
            "azure_doc_intelligence": bool(
                self.azure_doc_intelligence.endpoint and self.azure_doc_intelligence.api_key
            ),
        }
        return status

    def is_production_ready(self) -> bool:
        """Check if all critical services are configured."""
        status = self.validate_azure_services()
        return all(status.values())


# Global singleton
settings = Settings()
