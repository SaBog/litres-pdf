import os
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

import requests
from tqdm import tqdm

from ..config import logger, settings
from ..models import Book

PAGE_URL_TEMPLATE = "https://www.litres.ru/pages/get_pdf_page/?file={file_id}&page={page_num}&rt=w{w}&ft={file_type}"

DEFAULT_MAX_RETRIES = 5
DEFAULT_INITIAL_DELAY = 0.5
DEFAULT_CHUNK_SIZE = 8192

class PageDownloader:
    """Handles downloading book pages with retry logic and progress tracking."""

    def __init__(self, session: requests.Session):
        self._session = session

    def download_pages(self, book: Book, image_dir: str, existing_pages: List[int]) -> None:
        """Download all missing pages for a book."""
        pages_to_download = sorted(set(range(book.total_pages)) - set(existing_pages))
        total_to_download = len(pages_to_download)

        if not total_to_download:
            logger.info("All pages already downloaded")
            return

        logger.info(f"Pages to download: {total_to_download}")
        start_time = time.time()
        max_workers = getattr(settings, 'max_workers', 5)

        with tqdm(total=total_to_download, unit='page', desc="Downloading", ncols=100, colour='green') as pbar:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self._download_page, page_num, book, image_dir): page_num
                    for page_num in pages_to_download
                }

                for future in as_completed(futures):
                    page_num = futures[future]
                    try:
                        if not future.result():
                            logger.warning(f"Page {page_num} download failed")
                    except Exception as e:
                        logger.error(f"Execution error for page {page_num}: {str(e)}")
                    finally:
                        pbar.update(1)

        elapsed = time.time() - start_time
        logger.info(f"Download completed: {total_to_download} pages in {elapsed:.1f} seconds")

    def _download_page(self, page_num: int, book: Book, image_dir: str) -> Optional[str]:
        """Download a single page with retry logic."""
        page = book.pages[page_num]
        url = PAGE_URL_TEMPLATE.format(
            file_id=book.file_id,
            page_num=page_num,
            w=page.width,
            file_type=page.extension
        )
        
        filename = f"page_{page_num:04d}.{page.extension}"
        filepath = os.path.join(image_dir, filename)

        max_retries = getattr(settings, 'max_retries', DEFAULT_MAX_RETRIES)
        initial_delay = getattr(settings, 'initial_delay', DEFAULT_INITIAL_DELAY)
        chunk_size = getattr(settings, 'chunk_size', DEFAULT_CHUNK_SIZE)

        for attempt in range(max_retries):
            try:
                delay = initial_delay * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(delay)

                response = self._session.get(url, stream=True, timeout=30)
                response.raise_for_status()

                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size):
                        f.write(chunk)
                
                logger.debug(f"Page {page_num} saved successfully")
                return filepath
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code
                if status == 429:
                    retry_after = int(e.response.headers.get('Retry-After', 15))
                    wait_time = retry_after * (attempt + 1)
                    logger.warning(f"Page {page_num}: Rate limit exceeded. Waiting {wait_time} seconds")
                    time.sleep(wait_time)
                elif status >= 500:
                    logger.warning(f"Page {page_num}: Server error ({status})")
                else:
                    logger.warning(f"Page {page_num}: HTTP error {status}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Page {page_num}: Network error: {str(e)}")
        
        logger.error(f"Failed to download page {page_num} after {max_retries} attempts")
        return None 