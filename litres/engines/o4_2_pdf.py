# o4_2_pdf.py
import os
from pathlib import Path
import re
from typing import List, Literal, Tuple, Dict
from fpdf import FPDF
from PIL import Image
from tqdm import tqdm
from litres.engines.base import Engine, OutFormat
from litres.engines.base_content_processor import BaseContentProcessor
from litres.models.output_path_handler import OutputPathHandler
from litres.models.book import Book
from litres.config import logger, app_settings
from litres.utils import load_and_parse_content

FontStyle = Literal["", "B", "I", "BI"]


class PDFContentProcessor(BaseContentProcessor):
    @classmethod
    def _escape(cls, text: str) -> str:
        return text  # No escaping for PDF
    
    @classmethod
    def _handle_special_tags(cls, node_type, node, content, context):
        if node_type in ('p', 'div'):
            # Remove soft hyphens (­) that appear visually but not in copy
            content = content.replace('&#173;', '')
            return f"\n{content}\n"
        
        if node_type in ('h1', 'h2', 'h3', 'title'):
            context['is_heading'] = True
            context['last_heading_level'] = 1 if node_type == "title" else int(node_type[1])
            return f"\n{content}\n"
        
        context['is_heading'] = False

        if node_type == 'br':
            return "\n"
        
        if node_type == 'hr':
            return "\n" + "-" * 50 + "\n"
        
        return content

    @classmethod
    def _generate_image_reference(cls, image_path, src, context):
        context['images'].append(image_path)
        return f"\n[IMAGE: {image_path.name}]\n"

class PDFBuilder:
    def __init__(self, book: Book):
        self.pdf = FPDF()
        self.book = book
        self._setup()

    def register_font(self, pdf: FPDF, family: str, base_path: str):
        """Registers regular, bold, italic, and bold-italic variants of a font."""

        variants: dict[FontStyle, str] = {
            "": "Regular",
            "B": "Bold",
            "I": "Italic",
            "BI": "BoldItalic"
        }

        for style, suffix in variants.items():
            font_path = os.path.join(base_path, f"{family}-{suffix}.ttf")
            if os.path.isfile(font_path):
                pdf.add_font(
                    family=family,
                    style=style,
                    fname=font_path,
                    uni=True
                )

        self.default_font = family
        
    def _setup(self):
        """Alternative using absolute paths"""
        self.register_font(self.pdf, "NotoSans", "fonts")

        self.pdf.add_page()
        self.pdf.set_font(self.default_font, size=12)
        self.pdf.set_auto_page_break(True, margin=20)

    def iter_lines(self, content: str):
        """Yield (line, is_heading) for all content lines."""
        pattern = re.compile(r'\[HEADING\](.*?)\[/HEADING\]', re.DOTALL)
        pos = 0
        for match in pattern.finditer(content):
            # Обычный текст до heading
            pre_text = content[pos:match.start()].strip()
            if pre_text:
                for line in pre_text.split('\n'):
                    yield line.strip(), False

            # Текст внутри heading
            heading_text = match.group(1).strip()
            for line in heading_text.split('\n'):
                yield line.strip(), True

            pos = match.end()

        # Текст после последнего heading
        rest = content[pos:].strip()
        if rest:
            for line in rest.split('\n'):
                yield line.strip(), False


    def add_content(self, content: str, images: List[Path]):
        lines = list(self.iter_lines(content))
        for line, is_heading in tqdm(lines, desc="Building PDF"):
            if not line:
                continue

            if line.startswith('[IMAGE: '):
                self._add_image(line, images)
            else:
                self._add_text(line, heading=is_heading)

    def _add_text(self, text: str, heading: bool = False):
        if heading:
            self.pdf.set_font(self.default_font, 'B', 16)
            self.pdf.multi_cell(
                0,
                7,
                text,
                align='L',
                ln=True,
                max_line_height=self.pdf.font_size * 1.5
            )
            self.pdf.ln(4)
        else:
            self.pdf.set_font(self.default_font, '', 12)
            # Indent first line manually with spaces
            indent = " " * 4
            text = indent + text
            self.pdf.multi_cell(
                0,
                5,
                text,
                align='J',
                ln=True,
                max_line_height=self.pdf.font_size * 1.15
            )
            self.pdf.ln(3)


    def _add_image(self, image_line: str, images: List[Path]):
        name = image_line[8:-1]
        if img := next((i for i in images if i.name == name), None):
            try:
                with Image.open(img) as image:
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    temp = Path("temp_img.jpg")
                    image.save(temp, "JPEG")
                    self.pdf.image(str(temp), x=10, w=180)
                    self.pdf.ln(10)
                    temp.unlink()
            except Exception as e:
                logger.error(f"Failed to process image {img}: {str(e)}")

    def save(self, output_path: Path):
        self.pdf.output(str(output_path))

class O4ToPDFEngine(Engine):
    SUPPORTED_OUT_FORMAT = OutFormat.PDF

    def execute(self, book, path: OutputPathHandler):
        try:
            if not (content := load_and_parse_content(path.source)):
                logger.error("No valid content found")
                return
            
            img_dir = path.source / app_settings.SOURCE_IMAGE_FOLDER
            pdf_content, images = self._process(content, img_dir)
            
            pdf_builder = PDFBuilder(book)
            pdf_builder.add_content(pdf_content, images)
            pdf_builder.save(path.output / (path.filename + '.pdf'))
            
            logger.info(f"PDF saved to: {path.output}")
        except Exception as e:
            logger.error(f"Failed to generate PDF: {str(e)}")

    def _process(self, struct: List[dict], img_dir: Path) -> Tuple[str, List[Path]]:
        context = {'images': [], 'last_heading_level': 0, 'is_heading': False}
        content = []

        for node in struct:
            context['is_heading'] = False
            text = PDFContentProcessor.process_node(node, img_dir, context)
            if context['is_heading']:
                # Mark headings explicitly
                content.append(f"[HEADING]{text.strip()}[/HEADING]")
            else:
                content.append(text)

        return ''.join(content), context['images']
