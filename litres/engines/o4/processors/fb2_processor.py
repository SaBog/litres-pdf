import base64
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

from litres.config import logger
from litres.constants import SUPPORTED_IMAGE_EXTENSIONS
from litres.engines.o4.processors.content_processor import (
    BaseContentProcessor, ContentNode)


class ImageIdGenerator:
    """Generates unique IDs for images"""
    
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
    """Processes content for FB2 format"""
    
    TAG_MAPPING = {
        'p': 'p',
        'em': 'emphasis',
        'strong': 'strong',
        'div': 'section',
        'h1': 'subtitle',
        'h2': 'subtitle',
        'h3': 'subtitle',
        'title': 'title',
        'blockquote': 'cite',
    }
    
    def _init_context(self) -> Dict[str, Any]:
        return {
            'img_id_gen': ImageIdGenerator(),
            'images': []
        }
    
    def _process_node_type(self, node: ContentNode, content: str) -> str:
        """Process node types specific to FB2"""
        if node.type in ('br', 'hr'):
            return '<empty-line/>'
        
        if node.type and (fb2_tag := self.TAG_MAPPING.get(node.type)):
            return f'<{fb2_tag}>{content}</{fb2_tag}>'
        
        return content
    
    def _process_image(self, node: ContentNode) -> str:
        """Process image references for FB2"""
        src = node.get_image_src()
        if not src:
            logger.warning(f"No image src found in node: {node.type}")
            return ''
        
        # Check if image exists
        image_path = self.img_dir / src
        if not image_path.exists():
            logger.warning(f"Image not found: {image_path}")
            return ''
        
        img_id = self.context['img_id_gen'].get_id(src)
        self.context['images'].append(src)
        return f'<image l:href="#{img_id}"/>'
    
    def _get_image_src(self, node: ContentNode) -> Optional[str]:
        """Extract image source from node"""
        return node.get_image_src()
    
    def _escape_text(self, text: str) -> str:
        """Escape text for XML"""
        return escape(text)
    
    def _finalize_content(self, content_parts: List[str]) -> str:
        """Finalize FB2 content"""
        if not content_parts:
            return '<section><p></p></section>'
        
        # Wrap content in sections if needed
        wrapped_parts = []
        for part in content_parts:
            if not part.strip():
                continue
            if not any(part.startswith(f'<{tag}') for tag in ['section', 'title', 'subtitle']):
                wrapped_parts.append(f'<section>{part}</section>')
            else:
                wrapped_parts.append(part)
        
        return ''.join(wrapped_parts)
    
    def generate_binaries(self) -> str:
        """Generate binary section for embedded images"""
        binaries = []
        for src, img_id in self.context['img_id_gen'].items():
            binary = self._create_binary_section(src, img_id)
            if binary:
                binaries.append(binary)
        return '\n'.join(binaries)
    
    def _create_binary_section(self, src: str, img_id: str) -> Optional[str]:
        """Create binary section for an image"""
        try:
            image_path = self.img_dir / src
            if not image_path.exists():
                logger.warning(f"Image not found: {image_path}")
                return None
            
            data = image_path.read_bytes()
            ext = image_path.suffix.lower()
            mime_type = SUPPORTED_IMAGE_EXTENSIONS.get(ext, 'application/octet-stream')
            b64_data = base64.b64encode(data).decode('ascii')
            
            return f'<binary id="{img_id}" content-type="{mime_type}">{b64_data}</binary>'
        except Exception as e:
            logger.error(f"Failed to process image {src}: {e}")
            return None