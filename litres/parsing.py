"""Helpers for reading the structures LitRes returns, shared by the extractors."""

import json
import re

from litres.constants import FILE_DOWNLOAD_URL
from litres.models.book import Author, BookMeta, ExtraFile
from litres.utils import js_object_to_json

# Fallback when a part cannot be parsed: names seen so far are i_1.jpg and img_0.png
_IMAGE_NAME = re.compile(r"\b(?:i|img)_\d+\.\w+")


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


def image_names(part_text: str) -> list[str]:
    """Image file names a text part refers to, in sorted order.

    Reads the `s`/`src` of `img` nodes; if the part cannot be parsed, falls back
    to matching known naming patterns. Names that are not plain file names
    (path separators, dot prefixes) are dropped.
    """
    try:
        data = json.loads(js_object_to_json(part_text))
    except ValueError:
        names = set(_IMAGE_NAME.findall(part_text))
    else:
        names = set()

        def walk(node: object) -> None:
            if isinstance(node, dict):
                if node.get("t") == "img":
                    src = node.get("s") or node.get("src")
                    if isinstance(src, str):
                        names.add(src)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(data)
    return sorted(n for n in names if n and "/" not in n and "\\" not in n and not n.startswith("."))


def extra_files(art_id: str, files: list[dict]) -> list[ExtraFile]:
    """The files LitRes marks as additional material (bonus PDF, code archive).

    The listing also keeps old versions of a file as separate entries; one file
    name is downloaded once, from its newest entry (release date, then id).
    """
    newest: dict[str, dict] = {}
    for f in files:
        if not (f.get("is_additional") and f.get("filename")):
            continue
        current = newest.get(f["filename"])
        if current is None or _recency(f) > _recency(current):
            newest[f["filename"]] = f
    return [
        ExtraFile(
            filename=f["filename"],
            url=FILE_DOWNLOAD_URL.format(
                art_id=art_id, file_id=f["id"], filename=f["filename"]
            ),
        )
        for f in newest.values()
    ]


def _recency(entry: dict) -> tuple[str, int]:
    return (entry.get("release_date") or "", int(entry["id"]))
