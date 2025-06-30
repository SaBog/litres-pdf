import re
from urllib.parse import parse_qs, urlparse

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