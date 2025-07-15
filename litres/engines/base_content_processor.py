# utils.py
from pathlib import Path
from typing import Optional, Union
from xml.sax.saxutils import escape
from litres.config import logger

class BaseContentProcessor:
    """Базовый процессор контента"""
    TAG_MAPPING = {}
    IMAGE_TEMPLATE = ""
    
    @classmethod
    def process_node(
        cls, 
        node: Union[str, dict, list], 
        img_dir: Path, 
        context: dict
    ) -> str:
        if isinstance(node, str):
            return cls._escape(node)
        
        if isinstance(node, list):
            return ''.join(cls.process_node(child, img_dir, context) for child in node)
        
        node_type: Optional[str] = node.get('t')
        content = cls._process_content(node, img_dir, context)
        
        if node_type == 'img':
            return cls._process_image(node, img_dir, context)
        
        if fb2_tag := cls.TAG_MAPPING.get(node_type):
            return f'<{fb2_tag}>{content}</{fb2_tag}>'
        
        return cls._handle_special_tags(node_type, node, content, context)
    
    @classmethod
    def _escape(cls, text: str) -> str:
        return escape(text)

    @classmethod
    def _process_content(
        cls, 
        node: dict, 
        img_dir: Path, 
        context: dict
    ) -> str:
        children = node.get('c', [])
        if isinstance(children, list):
            return ''.join(cls.process_node(child, img_dir, context) for child in children)
        return cls._escape(str(children))
    
    @classmethod
    def _process_image(
        cls, 
        node: dict, 
        img_dir: Path, 
        context: dict
    ) -> str:
        src = node.get('s') or node.get('src')
        if not src:
            return ''
        
        if not img_dir:
            logger.warning(f"Image not found: {src}")
            return ''
        
        return cls._generate_image_reference(img_dir, src, context)
    
    @classmethod
    def _generate_image_reference(
        cls, 
        image_path: Path, 
        src: str, 
        context: dict
    ) -> str:
        raise NotImplementedError()

    @classmethod
    def _handle_special_tags(
        cls, 
        node_type: Optional[str], 
        node: dict, 
        content: str, 
        context: dict
    ) -> str:
        return content