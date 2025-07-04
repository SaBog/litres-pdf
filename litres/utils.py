import re
import time
from functools import wraps
from urllib.parse import parse_qs, urlparse
from litres.config import settings, logger

# Глобальные скомпилированные регулярки для парсинга JS-like JSON
key_re = re.compile(r'([{,]\s*)(\w+)(\s*:)')
comma_re = re.compile(r',\s*([}\]])')

def extract_base_url(url: str) -> str | None:
    """Extracts the base_url from a subscription book URL."""
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        return query_params.get('baseurl', [None])[0]
    except (AttributeError, IndexError):
        return None

def sanitize_filename(name):
    """Очистка имени файла от недопустимых символов"""
    return re.sub(r'[<>:"/\\|?*]', '_', str(name)).strip()[:100]

def extract_file_id(url):
    """Извлечение ID книги из URL"""
    # Пытаемся извлечь ID из параметров запроса
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    
    if 'file' in query_params:
        return query_params['file'][0]
    elif 'art' in query_params:
        return query_params['art'][0]
    
    # This is a more specific match for book URLs like /book/author/title-12345/
    path_match = re.search(r'/book/.*-(\d+)/?$', parsed_url.path)
    if path_match:
        return path_match.group(1)

    # Пробуем извлечь ID из пути URL
    match = re.search(r'reader/(?:or/)?(\d+)', url)
    if match:
        return match.group(1)
    
    # Пробуем извлечь ID из короткой формы URL
    match = re.search(r'litres\.ru/(\d+)/?', url)
    if match:
        return match.group(1)
    
    return None

def timing(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        logger.info(f"[{func.__name__}] executed in {end - start:.4f} seconds")
        return result
    return wrapper