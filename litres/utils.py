import json
from pathlib import Path
import re
import time
from functools import wraps
from typing import List
from litres.config import logger

# Глобальные скомпилированные регулярки для парсинга JS-like JSON
key_re = re.compile(r'([{,]\s*)(\w+)(\s*:)')
comma_re = re.compile(r',\s*([}\]])')

def timing(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        logger.debug(f"[{func.__name__}] executed in {end - start:.4f} seconds")
        return result
    return wrapper

def sanitize_filename(name):
    """Очистка имени файла от недопустимых символов"""
    return re.sub(r'[<>:"/\\|?*]', '_', str(name)).strip()[:100]

def extract_initial_state(html: str):
    """
    Extracts the 'initialState' JSON object from the given HTML string.
    Handles Russian and other Unicode characters correctly.
    """
    # Non-greedy match for the initialState value
    match = re.search(
        r'"initialState":"(.*?)"},"__N_SSP',
        html,
        re.DOTALL
    )
    if not match:
        raise ValueError("initialState not found in HTML")

    state_str_escaped = match.group(1)
    
    try:
        # First unescape the JSON string (handles \", \\, \/, \b, \f, \n, \r, \t, \uXXXX)
        state_str = json.loads(f'"{state_str_escaped}"')
        # Then parse the actual JSON
        state_json = json.loads(state_str)
    except Exception as e:
        raise ValueError(f"Failed to decode or parse initialState: {e}")

    return state_json

def load_and_parse_content(source_dir: Path) -> List[dict]:
    """Загрузка и парсинг контента из текстовых файлов"""
    content = []
    for file in sorted(source_dir.glob("*.txt")):
        try:
            file_content = file.read_text(encoding='utf-8').strip()
            if not file_content:
                continue
            
            try:
                parsed = json.loads(file_content)
            except json.JSONDecodeError:
                fixed = JSONFixer.fix_json_string(file_content)
                parsed = json.loads(fixed)
            
            if parsed:
                content.extend(parsed)
        except Exception as e:
            logger.error(f"Failed to process file {file}: {str(e)}")
    return content


class JSONFixer:
    """Helper class for fixing common JSON issues."""
    
    @staticmethod
    def fix_json_string(json_str: str) -> str:
        """Attempt to fix common JSON issues in the input string."""
        fixed = re.sub(r"(?<!\\)'", '"', json_str)
        fixed = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', fixed)
        return fixed.replace('True', 'true').replace('False', 'false').replace('None', 'null')
