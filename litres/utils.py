import json
import re
import time
from functools import wraps
from pathlib import Path

from litres.config import logger


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
    return re.sub(r'[<>:"/\\|?*]', "_", str(name)).strip()[:100]


def extract_initial_state(html: str):
    """
    Extracts the 'initialState' JSON object from the given HTML string.
    Handles Russian and other Unicode characters correctly.
    """
    # Non-greedy match for the initialState value
    match = re.search(r'"initialState":"(.*?)"},"__N_SSP', html, re.DOTALL)
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


def load_and_parse_content(source_dir: Path) -> list[dict]:
    """Загрузка и парсинг контента из текстовых файлов"""
    content = []
    for file in natural_sorted(source_dir.glob("*.txt")):
        try:
            file_content = file.read_text(encoding="utf-8").strip()
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
            logger.error(f"Failed to process file {file}: {e!s}")
    return content


class JSONFixer:
    """Helper class for fixing common JSON issues."""

    @staticmethod
    def fix_json_string(json_str: str) -> str:
        """Attempt to fix common JSON issues in the input string."""
        return js_object_to_json(json_str)


_BARE_LITERALS = {"True": "true", "False": "false", "None": "null", "undefined": "null"}


def _convert_string(text: str, start: int) -> tuple[str, int]:
    """Convert the quoted string starting at `start` to a JSON string literal.

    Returns the literal and the index just past the closing quote.
    """
    quote = text[start]
    i = start + 1
    buf: list[str] = []
    while i < len(text) and text[i] != quote:
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            buf.append("'" if nxt == "'" else ch + nxt)
            i += 2
            continue
        buf.append('\\"' if ch == '"' else ch)
        i += 1
    return '"' + "".join(buf) + '"', i + 1


def js_object_to_json(text: str) -> str:
    """Convert a JS-like object literal to JSON without touching string contents.

    Handles unquoted keys, single-quoted strings, trailing commas and
    Python/JS bare literals (True/False/None/undefined).
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in "\"'":
            literal, i = _convert_string(text, i)
            out.append(literal)
        elif ch.isalpha() or ch in "_$":
            j = i
            while j < n and (text[j].isalnum() or text[j] in "_$"):
                j += 1
            word = text[i:j]
            k = j
            while k < n and text[k].isspace():
                k += 1
            is_key = k < n and text[k] == ":"
            out.append(f'"{word}"' if is_key else _BARE_LITERALS.get(word, word))
            i = j
        elif ch == ",":
            k = i + 1
            while k < n and text[k].isspace():
                k += 1
            if not (k < n and text[k] in "}]"):
                out.append(ch)
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def natural_sorted(paths):
    """Sort paths so numeric stems go by value (2 before 10), others by name."""

    def key(path: Path):
        stem = path.stem
        return (0, int(stem), "") if stem.isdigit() else (1, 0, path.name)

    return sorted(paths, key=key)
