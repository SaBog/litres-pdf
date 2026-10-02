import requests

from litres.config import logger
from litres.exceptions import BookProcessingError
from litres.models.book import ExtraFile
from litres.parsing import extra_files
from litres.services.litres_api import LitresApi


def find_extras(api: LitresApi, art_id: str | None) -> list[ExtraFile]:
    """Additional files of an art; a failure here must not stop the book itself."""
    if not art_id:
        return []
    try:
        return extra_files(art_id, api.art_files(art_id))
    except (requests.RequestException, BookProcessingError) as e:
        logger.warning(f"Could not list additional files for art {art_id}: {e!s}")
        return []
