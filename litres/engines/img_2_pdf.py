import os
import tempfile

from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from fpdf import FPDF
from tqdm import tqdm

from litres.config import logger
from litres.engines.base import Engine, OutFormat
from litres.models.output_path_handler import OutputPathHandler


class IMG2PDFEngine(Engine):
    SUPPORTED_OUT_FORMAT = OutFormat.PDF

    def __init__(self, quality: int = 65, dpi: int = 150):
        if quality > 100:
            logger.warning(f"Invalid quality {quality}% clamped to 100%")
            quality = 100
        self.quality = quality
        self.dpi = dpi

    def _get_sorted_images(self, input_folder: Path) -> List[Path]:
        """Get sorted list of image files in the input folder."""
        image_files = sorted(
            list(input_folder.glob("*.jpg")) + 
            list(input_folder.glob("*.gif")),
            key=lambda x: int(x.stem)
        )
        return image_files
    
    def _process_image(self, img_path: Path, temp_dir: str, index: int) -> Optional[str]:
        """Process individual image and return temporary file path."""
        output_path = os.path.join(temp_dir, f"{index:04d}.jpg")
        try:
            with Image.open(str(img_path)) as img:
                if img.mode in ('P', 'RGBA', 'LA'):
                    img = img.convert('RGB')
                
                if self.dpi > 0:
                    a4_width_px = int(210 * self.dpi / 25.4)
                    a4_height_px = int(297 * self.dpi / 25.4)
                    
                    if img.width > a4_width_px or img.height > a4_height_px:
                        width_ratio = a4_width_px / img.width
                        height_ratio = a4_height_px / img.height
                        scale_factor = min(width_ratio, height_ratio)
                        
                        if scale_factor < 1.0:
                            new_width = int(img.width * scale_factor)
                            new_height = int(img.height * scale_factor)
                            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                img.save(output_path, format='JPEG', quality=self.quality, optimize=True)
                return output_path
                
        except Exception as e:
            logger.error(f"Error processing image {img_path}: {str(e)}")
            return None
    
    def execute(self, path: OutputPathHandler):
        """Create optimized PDF from a folder of images."""
        try:
            image_files = self._get_sorted_images(path.source)
            if not image_files:
                raise ValueError("No image files found in the input folder")
            
            logger.info(f"Processing {len(image_files)} images with quality={self.quality}%, DPI={self.dpi}")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Process images in parallel
                temp_paths = {}
                with ThreadPoolExecutor() as executor:
                    futures = {
                        executor.submit(self._process_image, img_path, temp_dir, idx): idx
                        for idx, img_path in enumerate(image_files)
                    }
                    
                    for future in tqdm(as_completed(futures), desc="Processing images", total=len(futures), unit="img", colour='green'):
                        idx = futures[future]
                        try:
                            temp_paths[idx] = future.result()
                        except Exception as e:
                            logger.error(f"Failed to process image {image_files[idx]}: {str(e)}")
                
                # Sort paths by index to maintain order
                sorted_temp_paths = [path for _, path in sorted(temp_paths.items())]
                
                # Check for processing failures
                failed_indices = [i for i, tp in enumerate(sorted_temp_paths) if tp is None]
                if failed_indices:
                    failed_files = [str(image_files[i]) for i in failed_indices]
                    raise ValueError(f"Failed to process images: {', '.join(failed_files)}")
                
                pdf = FPDF()
                pdf.set_auto_page_break(False)
                pdf.set_compression(True)
                
                for temp_path in tqdm(sorted_temp_paths, desc="Building PDF", total=len(sorted_temp_paths), unit="page", colour='green'):
                    if temp_path:
                        pdf.add_page()
                        pdf.image(temp_path, x=0, y=0, w=210, h=297, type='JPG')
                
                filename = path.output / (path.filename + '.pdf')
                pdf.output(str(filename))
        except Exception as e:
            logger.error(f"PDF optimization failed: {str(e)}", exc_info=True)
            raise
   