from litres.config import logger
from litres.constants import SOURCE_IMAGE_FOLDER
from litres.engines.base import Engine, OutFormat
from litres.engines.o4.processors.fb2_processor import FB2ContentProcessor
from litres.models.book import Book
from litres.models.output_path_handler import OutputPathHandler
from litres.utils import load_and_parse_content


class FB2Engine(Engine):
    """Simplified FB2 engine using the new content processor"""
    
    SUPPORTED_OUT_FORMAT = OutFormat.FB2
    
    def execute(self, book: Book, path: OutputPathHandler):
        try:
            content = load_and_parse_content(path.source)
            if not content:
                logger.error("No valid content found")
                return
            
            img_dir = path.source / SOURCE_IMAGE_FOLDER
            processor = FB2ContentProcessor(img_dir)
            
            # Process content
            body_content = processor.process_structure(content)
            binaries = processor.generate_binaries()
            
            # Build complete FB2
            fb2_content = self._build_fb2_document(book, body_content, binaries)
            
            # Save to file
            output_path = path.output / (path.filename + '.fb2')
            output_path.write_text(fb2_content, encoding='utf-8')
            
            logger.info(f"FB2 saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate FB2: {e}")
    
    def _build_fb2_document(self, book: Book, body_content: str, binaries: str) -> str:
        """Build complete FB2 document"""
        header = self._build_header(book)
        footer = f'</body>\n{binaries}\n</FictionBook>'
        return header + body_content + footer
    
    def _build_header(self, book: Book) -> str:
        """Build FB2 header"""
        title = book.meta.title or "Untitled"
        authors = self._build_authors_xml(book.meta.authors)
        
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
    
    def _build_authors_xml(self, authors) -> str:
        """Build authors XML section"""
        if not authors:
            return '<author><first-name>Unknown</first-name></author>'
        
        xml_parts = []
        for author in authors:
            parts = [f'<first-name>{author.first or "Unknown"}</first-name>']
            if author.middle:
                parts.append(f'<middle-name>{author.middle}</middle-name>')
            if author.last:
                parts.append(f'<last-name>{author.last}</last-name>')
            
            xml_parts.append(f'<author>{"".join(parts)}</author>')
        
        return ''.join(xml_parts)