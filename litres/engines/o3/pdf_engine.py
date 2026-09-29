import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple

from fpdf import FPDF
from PIL import Image
from tqdm import tqdm

from litres.config import logger
from litres.engines.base import Engine
from litres.models.book import BookMeta, PdfBook
from litres.models.book_paths import BookPaths
from litres.models.out_format import OutFormat

A4_WIDTH = 210
A4_HEIGHT = 297


class ProcessedImage(NamedTuple):
    data: io.BytesIO
    width: int
    height: int


class IMG2PDFEngine(Engine[PdfBook]):
    SUPPORTED_OUT_FORMAT = OutFormat.PDF

    def __init__(self, quality: int = 65, dpi: int = 150):
        self.quality = min(quality, 100)
        self.dpi = dpi

        self.a4_width = int(A4_WIDTH * self.dpi / 25.4)
        self.a4_height = int(A4_HEIGHT * self.dpi / 25.4)

    def execute(self, book: PdfBook, path: BookPaths) -> None:
        try:
            images = self._get_images(path.source)
            if not images:
                raise ValueError("No images found")

            logger.info(
                f"Processing {len(images)} images (Q: {self.quality}%, DPI: {self.dpi})"
            )

            # Обработка изображений полностью в памяти
            image_data = self._process_images(images)
            self._create_pdf(
                book.meta, image_data, path.output / (path.filename + ".pdf")
            )
        except Exception as e:
            logger.error(f"PDF creation failed: {e!s}", exc_info=True)
            raise

    def _get_images(self, input_folder: Path) -> list[Path]:
        """Get sorted list of image files in the input folder."""
        image_files = sorted(
            [f for f in input_folder.glob("*.jpg") if f.is_file()]
            + [f for f in input_folder.glob("*.gif") if f.is_file()],
        )
        return image_files

    def _process_images(self, images: list[Path]) -> dict[Path, ProcessedImage]:
        """Обработка изображений с возвратом данных в памяти"""
        processed = {}
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(self._process_image, img): img for img in images}
            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Processing",
                unit="img",
                colour="green",
            ):
                img_path = futures[future]
                result = future.result()
                if result:
                    processed[img_path] = result
        return processed

    def _process_image(self, img_path: Path) -> ProcessedImage | None:
        """Обработка одного изображения с возвратом BytesIO"""
        try:
            with Image.open(img_path) as img:
                # Конвертация в RGB при необходимости
                if img.mode != "RGB":
                    img = img.convert("RGB")

                # Ресайз при необходимости
                if self.dpi > 0 and (
                    img.width > self.a4_width or img.height > self.a4_height
                ):
                    scale = min(self.a4_width / img.width, self.a4_height / img.height)
                    new_size = (int(img.width * scale), int(img.height * scale))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)

                # Сохранение в память вместо файла
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="JPEG", quality=self.quality, optimize=True)
                img_bytes.seek(0)  # Сброс указателя в начало
                return ProcessedImage(img_bytes, img.width, img.height)
        except Exception as e:
            logger.error(f"Error processing {img_path}: {e!s}")
            return None

    def _create_pdf(
        self, meta: BookMeta, image_data: dict[Path, ProcessedImage], output_path: Path
    ):
        """Создание PDF из данных в памяти"""
        pdf = FPDF()
        pdf.set_auto_page_break(False)
        pdf.set_compression(True)

        # Установка метаданных
        pdf.set_title(meta.title)
        pdf.set_author(", ".join(author.first for author in meta.authors))
        pdf.set_creator(f"LitRes Converter v{meta.version}")
        pdf.set_subject(f"Book UUID: {meta.uuid}")

        # Сохранение порядка изображений
        sorted_images = sorted(
            image_data.items(),
            key=lambda x: int(x[0].stem),  # Сортировка по числу в имени файла
        )

        for img_path, image in tqdm(
            sorted_images, desc="Building PDF", unit="page", colour="green"
        ):
            # Страница A4 по ширине, высота по пропорциям исходной картинки
            page_height = A4_WIDTH * image.height / image.width
            # fpdf2 accepts a (width, height) tuple; its annotation says str only
            pdf.add_page(format=(A4_WIDTH, page_height))  # ty: ignore[invalid-argument-type]
            pdf.image(image.data, x=0, y=0, w=A4_WIDTH, h=page_height)
            image.data.close()  # Важно: закрываем поток после использования

        pdf.output(str(output_path))
