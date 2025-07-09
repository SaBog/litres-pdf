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