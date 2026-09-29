"""Helpers for reading the structures LitRes returns, shared by the extractors."""

from litres.models.book import Author, BookMeta


def state_queries(state: dict) -> dict:
    """The RTK Query cache inside a page's initialState."""
    return state.get("rtkqApi", {}).get("queries", {})


def find_query(state: dict, key_prefix: str) -> tuple[str, dict] | None:
    """First cached query whose key starts with key_prefix, as (key, value)."""
    for key, value in state_queries(state).items():
        if key.startswith(key_prefix):
            return key, value
    return None


def book_meta_from_dict(
    meta_data: dict, *, default_title: str, default_uuid: str
) -> BookMeta:
    """Build BookMeta from a LitRes `Meta` object (capitalised keys)."""
    authors = [
        Author(
            first=author.get("First", ""),
            middle=author.get("Middle") or None,
            last=author.get("Last") or None,
        )
        for author in meta_data.get("Authors", [])
        if isinstance(author, dict)
    ]
    return BookMeta(
        authors=authors,
        title=meta_data.get("Title", default_title),
        version=float(meta_data.get("version") or 0.0),
        uuid=meta_data.get("UUID", default_uuid),
    )
