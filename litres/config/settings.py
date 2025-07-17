from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from litres.engines.base import OutFormat


class AppSettings(BaseSettings):
    # Configuration model with default values
    test_mode: bool = False
    cookie_file: Path = Path("cookies.json")
    max_workers: int = 4
    delay: float = 1.0
    quality: int = 65
    dpi: int = 300
    source_dir: str = 'books-source'
    books_dir: str = 'books'

    out_format_priority: List[OutFormat] = [OutFormat.PDF, OutFormat.FB2, OutFormat.MP3]

    @field_validator('out_format_priority', mode='before')
    @classmethod
    def parse_out_format_priority(cls, v):
        if isinstance(v, str):
            return [OutFormat(item.strip().lower()) for item in v.split(",")]
        return v
    
    # Configuration sources
    model_config = SettingsConfigDict(
        env_file="config.ini",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore"
    )


app_settings = AppSettings()