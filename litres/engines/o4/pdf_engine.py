import io
import os
from pathlib import Path
from typing import List, Literal

from fpdf import FPDF
from PIL import Image
from tqdm import tqdm

from litres.config import logger
from litres.constants import SOURCE_IMAGE_FOLDER
from litres.engines.base import Engine, OutFormat
from litres.engines.o4.processors.pdf_processor import PDFContentProcessor
from litres.models.book import Book
from litres.models.output_path_handler import OutputPathHandler
from litres.utils import load_and_parse_content


class PDFEngine(Engine):
    """Simplified PDF engine using the new content processor"""
    
    SUPPORTED_OUT_FORMAT = OutFormat.PDF
    
    def execute(self, book: Book, path: OutputPathHandler):
        try:
            content = load_and_parse_content(path.source)
            if not content:
                logger.error("No valid content found")
                return
            
            img_dir = path.source / SOURCE_IMAGE_FOLDER
            # debug_image_nodes(content, img_dir)

            processor = PDFContentProcessor(img_dir)
            
            # Process content
            pdf_content = processor.process_structure(content)
            images = processor.get_images()
            
            # Build PDF
            pdf_builder = PDFBuilder(book)
            lines = processor.parse_content_with_headings(pdf_content)
            
            for line_text, is_heading in tqdm(lines, desc="Building PDF", colour='green'):
                if not line_text:
                    continue
                    
                if line_text.startswith('[IMAGE: '):
                    pdf_builder.add_image(line_text, images)
                else:
                    pdf_builder.add_text(line_text, heading=is_heading)
            
            # Save PDF
            output_path = path.output / (path.filename + '.pdf')
            pdf_builder.save(output_path)
            
            logger.info(f"PDF saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate PDF: {e}")

class PDFBuilder:
    """Handles PDF construction with proper font management"""
    
    def __init__(self, book: Book):
        self.pdf = FPDF()
        self.book = book
        self.default_font = "NotoSans"
        self._setup()
    
    def _setup(self):
        """Setup PDF with fonts and initial page"""
        self._register_fonts()
        self.pdf.add_page()
        self.pdf.set_font(self.default_font, size=12)
        self.pdf.set_auto_page_break(True, margin=20)
    
    def _register_fonts(self):
        """Register font family with all variants"""
        font_variants: dict[Literal["", "B", "I", "BI"], str] = {
            "": "Regular",
            "B": "Bold", 
            "I": "Italic",
            "BI": "BoldItalic"
        }
        
        for style, suffix in font_variants.items():
            font_path = f"fonts/{self.default_font}-{suffix}.ttf"
            if os.path.isfile(font_path):
                self.pdf.add_font(
                    family=self.default_font,
                    style=style,
                    fname=font_path,
                    uni=True
                )
    
    def add_text(self, text: str, heading: bool = False):
        """Add text to PDF with proper formatting"""
        if heading:
            self.pdf.set_font(self.default_font, 'B', 16)
            self.pdf.multi_cell(
                0, 7, text,
                align='L', ln=True,
                max_line_height=self.pdf.font_size * 1.15
            )
            self.pdf.ln(4)
        else:
            self.pdf.set_font(self.default_font, '', 12)
            # Add paragraph indentation
            indented_text = "    " + text
            self.pdf.multi_cell(
                0, 5, indented_text,
                align='J', ln=True,
                max_line_height=self.pdf.font_size * 1.15
            )
            self.pdf.ln(3)
    
    def add_image(self, image_line: str, images: List[Path]):
        """Add image to PDF"""
        # Extract image name from [IMAGE: filename] format
        image_name = image_line[8:-1]
        
        # Find matching image
        image_path = next((img for img in images if img.name == image_name), None)
        if not image_path:
            logger.warning(f"Image not found: {image_name}")
            return
        
        try:
            with Image.open(image_path) as img:
                # Конвертация в RGB при необходимости
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Используем буфер в памяти вместо файла
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG')
                img_byte_arr.seek(0)  # Сбрасываем указатель в начало
                
                # Добавляем в PDF из памяти
                self.pdf.image(img_byte_arr, x=10, w=180)
                self.pdf.ln(10)
        except Exception as e:
            logger.error(f"Failed to process image {image_path}: {e}")
    
    def save(self, output_path: Path):
        """Save PDF to file"""
        self.pdf.output(str(output_path))