import tempfile
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from fpdf import FPDF
from tqdm import tqdm

from litres.engines.base import Engine, OutFormat
from litres.config import logger
from litres.models.book import BookMeta
from litres.models.output_path_handler import OutputPathHandler

A4_WIDTH = 210
A4_HEIGHT = 297 

class IMG2PDFEngine(Engine):
    SUPPORTED_OUT_FORMAT = OutFormat.PDF

    def __init__(self, quality: int = 65, dpi: int = 150):
        self.quality = min(quality, 100)
        self.dpi = dpi

        self.a4_width = int(A4_WIDTH * self.dpi / 25.4)  
        self.a4_height = int(A4_HEIGHT * self.dpi / 25.4)  

    def execute(self, book, path: OutputPathHandler):
        try:
            images = self._get_images(path.source)
            if not images:
                raise ValueError("No images found")
            
            logger.info(f"Processing {len(images)} images (Q: {self.quality}%, DPI: {self.dpi})")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_paths = self._process_images(images, temp_dir)
                self._create_pdf(book.meta, temp_paths, path.output / (path.filename + '.pdf'))
        except Exception as e:
            logger.error(f"PDF creation failed: {str(e)}", exc_info=True)
            raise

    def _get_images(self, input_folder: Path) -> List[Path]:
        """Get sorted list of image files in the input folder."""
        image_files = sorted(
            list(input_folder.glob("*.jpg")) + 
            list(input_folder.glob("*.gif")),
            key=lambda x: int(x.stem)
        )
        return image_files
    
    def _process_images(self, images: List[Path], temp_dir: str) -> List[Path]:
        temp_paths = {}
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(self._process_image, img, temp_dir): img for img in images}
            for future in tqdm(as_completed(futures), total=len(futures), desc="Processing", unit="img"):
                if result := future.result():
                    temp_paths[futures[future]] = result
        return [temp_paths[img] for img in images if img in temp_paths]

    def _process_image(self, img_path: Path, temp_dir: str) -> Optional[Path]:
        try:
            output_path = Path(temp_dir) / f"{img_path.stem}.jpg"
            
            with Image.open(img_path) as img:
                # Convert image modes that can't be saved as JPEG
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Only resize if DPI is specified and image exceeds A4 dimensions
                if self.dpi > 0:
                    # Calculate scaling factor if needed
                    if img.width > self.a4_width or img.height > self.a4_height:
                        scale = min(self.a4_width / img.width, self.a4_height / img.height)
                        new_size = (int(img.width * scale), int(img.height * scale))
                        img = img.resize(new_size, Image.Resampling.LANCZOS)

                    img.save(
                        output_path, 
                        format='JPEG', 
                        quality=self.quality, 
                        optimize=True
                    )
                return output_path
        except Exception as e:
            logger.error(f"Error processing {img_path}: {str(e)}")
            return None

    def _create_pdf(self, meta: BookMeta, image_paths: List[Path], output_path: Path):
        pdf = FPDF()
        pdf.set_auto_page_break(False)
        pdf.set_compression(True)

        # Set document metadata
        pdf.set_title(meta.title)
        pdf.set_author(", ".join(author.first for author in meta.authors))
        pdf.set_creator(f"LitRes Converter v{meta.version}")
        pdf.set_subject(f"Book UUID: {meta.uuid}")
        
        for img_path in tqdm(image_paths, desc="Building PDF", unit="page"):
            pdf.add_page()
            pdf.image(str(img_path), x=0, y=0, w=A4_WIDTH, h=A4_HEIGHT)
        
        pdf.output(str(output_path))