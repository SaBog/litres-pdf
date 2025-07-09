import json
import re
import time
from functools import wraps

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

import re
import json

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