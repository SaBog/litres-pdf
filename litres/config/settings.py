from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    # Configuration model with default values
    test_mode: bool = False
    cookie_file: Path = Path("cookies.json")
    max_workers: int = 4
    delay: float = 1.0
    quality: int = 65
    dpi: int = 300
    domain: str = 'https://www.litres.ru/'
    source_dir: str = 'books-source'
    books_dir: str = 'books'

    # Configuration sources
    model_config = SettingsConfigDict(
        env_file="config.ini",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore"
    )


settings = AppSettings()