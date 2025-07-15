# o4_2_fb2.py
import base64
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from litres.engines.base_content_processor import BaseContentProcessor
from litres.models.book import Book
from litres.utils import load_and_parse_content
from litres.engines.base import Engine, OutFormat
from litres.models.output_path_handler import OutputPathHandler
from litres.config import logger, app_settings

FB2_FOOTER = '</body>\n{binaries}\n</FictionBook>'

class ImageIdGenerator:
    """Генератор уникальных ID для изображений"""
    __slots__ = ('counter', 'mapping')
    
    def __init__(self):
        self.counter = 1
        self.mapping: Dict[str, str] = {}

    def get_id(self, src: str) -> str:
        if src not in self.mapping:
            self.mapping[src] = f"img{self.counter}"
            self.counter += 1
        return self.mapping[src]

    def items(self) -> List[Tuple[str, str]]:
        return list(self.mapping.items())

class FB2ContentProcessor(BaseContentProcessor):
    TAG_MAPPING = {
        'p': 'p',
        'em': 'emphasis',
        'strong': 'strong',
        'div': 'section',
        'h1': 'subtitle',
        'h2': 'subtitle',
        'h3': 'subtitle',
    }
    
    @classmethod
    def _handle_special_tags(cls, node_type, node, content, context):
        if node_type in ('br', 'hr'):
            return '<empty-line/>'
        
        if (isinstance(node.get('c'), list) and 
            all(isinstance(x, str) for x in node['c'])):
            return '&#173;'.join(node['c'])
        
        return content

    @classmethod
    def _generate_image_reference(cls, image_path, src, context):
        img_id_gen = context['img_id_gen']
        img_id = img_id_gen.get_id(src)
        return f'<image l:href="#{img_id}"/>'

class FB2Builder:
    @staticmethod
    def build_header(book: Book) -> str:
        title = book.meta.title or "Untitled"
        authors = FB2Builder._build_authors_xml(book.meta.authors)
        
        return f'''<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" xmlns:l="http://www.w3.org/1999/xlink">
<description>
<title-info>
<genre>prose</genre>
{authors}
<book-title>{title}</book-title>
<lang>ru</lang>
</title-info>
</description>
<body>
'''

    @staticmethod
    def _build_authors_xml(authors) -> str:
        if not authors:
            return '<author><first-name>Unknown</first-name></author>'
        
        xml = []
        for author in authors:
            parts = [f'<first-name>{author.first or "Unknown"}</first-name>']
            if author.middle:
                parts.append(f'<middle-name>{author.middle}</middle-name>')
            if author.last:
                parts.append(f'<last-name>{author.last}</last-name>')
                
            xml.append(f'<author>{"".join(parts)}</author>')
        return ''.join(xml)

    @staticmethod
    def build_binary_section(image_path: Path, image_id: str) -> Optional[str]:
        try:
            data = image_path.read_bytes()
            ext = image_path.suffix.lower()
            mime_type = app_settings.SUPPORTED_IMAGE_EXTENSIONS.get(ext, 'application/octet-stream')
            b64_data = base64.b64encode(data).decode('ascii')
            return f'<binary id="{image_id}" content-type="{mime_type}">{b64_data}</binary>'
        except Exception as e:
            logger.error(f"Failed to process image {image_path}: {str(e)}")
            return None

class FB2Converter:
    @staticmethod
    def convert(struct: List[dict], img_dir: Path, book) -> str:
        img_id_gen = ImageIdGenerator()
        context = {'img_id_gen': img_id_gen}
        
        body_content = FB2Converter._build_body(struct, img_dir, context)
        binaries = FB2Converter._build_binaries(img_dir, img_id_gen)
        
        header = FB2Builder.build_header(book)
        return header + ''.join(body_content) + FB2_FOOTER.format(binaries=binaries)

    @staticmethod
    def _build_body(struct: List[dict], img_dir: Path, context: dict) -> List[str]:
        content = []
        for node in struct:
            node_content = FB2ContentProcessor.process_node(node, img_dir, context)
            if not node_content:
                continue
            
            tag = 'section' if not (isinstance(node, dict) and node.get('t') == 'div') else ''
            content.append(f'<{tag}>{node_content}</{tag}>' if tag else node_content)
        
        return content or ['<section><p></p></section>']

    @staticmethod
    def _build_binaries(img_dir: Path, img_id_gen: ImageIdGenerator) -> str:
        binaries = []
        for _, img_id in img_id_gen.items():
            if binary := FB2Builder.build_binary_section(img_dir, img_id):
                binaries.append(binary)
        return '\n'.join(binaries)

class O4ToFB2Engine(Engine):
    SUPPORTED_OUT_FORMAT = OutFormat.FB2

    def execute(self, book, path: OutputPathHandler):
        try:
            if not (content := load_and_parse_content(path.source)):
                logger.error("No valid content found")
                return
            
            img_dir = path.source / app_settings.SOURCE_IMAGE_FOLDER
            fb2_text = FB2Converter.convert(content, img_dir, book)
            
            output_path = path.output / (path.filename + '.fb2')
            output_path.write_text(fb2_text, encoding='utf-8')
            logger.info(f"FB2 saved to: {output_path}")
        except Exception as e:
            logger.error(f"Failed to generate FB2: {str(e)}")