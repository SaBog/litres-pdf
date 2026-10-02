DOMAIN: str = "https://www.litres.ru/"
SOURCE_IMAGE_FOLDER: str = "images"
FILE_DOWNLOAD_URL: str = (
    DOMAIN + "download_book_subscr/{art_id}/{file_id}/{filename}"
)
SUPPORTED_IMAGE_EXTENSIONS: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
}
