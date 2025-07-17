import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from litres.config import logger
from litres.engines.o4.processors.content_processor import (
    BaseContentProcessor, ContentNode)


class PDFContentProcessor(BaseContentProcessor):
    """Processes content for PDF format"""
    
    def _init_context(self) -> Dict[str, Any]:
        return {
            'images': [],
            'headings': []
        }
    
    def _process_node_type(self, node: ContentNode, content: str) -> str:
        """Process node types specific to PDF"""
        if node.type in ('p', 'div'):
            return f"\n{content}\n"
        
        if node.type in ('h1', 'h2', 'h3', 'title'):
            self.context['headings'].append(content.strip())
            return f"\n[HEADING]{content.strip()}[/HEADING]\n"
        
        if node.type == 'br':
            return "\n"
        
        if node.type == 'hr':
            return "\n" + "-" * 50 + "\n"
        
        if node.type == 'blockquote':
            # Indent blockquote content
            indented = '\n'.join(f"    {line}" for line in content.split('\n') if line.strip())
            return f"\n{indented}\n"
        
        return content
    
    def _process_image(self, node: ContentNode) -> str:
        """Process image references for PDF"""
        src = self._get_image_src(node)
        if not src:
            return ''
        
        image_path = self.img_dir / src
        if image_path.exists():
            self.context['images'].append(image_path)
            return f"\n[IMAGE: {image_path.name}]\n"
        else:
            logger.warning(f"Image not found: {image_path}")
            return ''
    
    def _get_image_src(self, node: ContentNode) -> Optional[str]:
        """Extract image source from node"""
        return node.get_image_src()
    
    def _escape_text(self, text: str) -> str:
        """No escaping needed for PDF"""
        return text
    
    def _finalize_content(self, content_parts: List[str]) -> str:
        """Finalize PDF content"""
        return ''.join(content_parts)
    
    def get_images(self) -> List[Path]:
        """Get list of processed images"""
        return self.context['images']
    
    def parse_content_with_headings(self, content: str) -> List[Tuple[str, bool]]:
        """Parse content and identify headings"""
        lines = []
        pattern = re.compile(r'\[HEADING\](.*?)\[/HEADING\]', re.DOTALL)
        pos = 0
        
        for match in pattern.finditer(content):
            # Regular text before heading
            pre_text = content[pos:match.start()].strip()
            if pre_text:
                for line in pre_text.split('\n'):
                    line = line.strip()
                    if line:
                        lines.append((line, False))
            
            # Heading text
            heading_text = match.group(1).strip()
            if heading_text:
                for line in heading_text.split('\n'):
                    line = line.strip()
                    if line:
                        lines.append((line, True))
            
            pos = match.end()
        
        # Text after last heading
        rest = content[pos:].strip()
        if rest:
            for line in rest.split('\n'):
                line = line.strip()
                if line:
                    lines.append((line, False))
        
        return lines