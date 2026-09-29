from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ContentNode:
    """Represents a structured content node with type, xpath, and content"""

    def __init__(self, data: dict[str, Any]):
        self.type: str | None = data.get("t")
        self.xpath: list[int] | None = data.get("xp")
        self.content: str | list[Any] = data.get("c", [])

        self.data = data

    def is_text_node(self) -> bool:
        """Check if this node contains only text content"""
        return isinstance(self.content, list) and all(
            isinstance(x, str) for x in self.content
        )

    def get_text(self) -> str:
        """Extract text content, handling soft hyphens"""
        if isinstance(self.content, str):
            return self.content
        elif self.is_text_node():
            # Join text fragments, removing soft hyphens
            return "".join(self.content).replace("\u00ad", "")
        return ""

    def get_image_src(self) -> str | None:
        """Image source name for <img> nodes (`s` or `src` key)"""
        if self.type != "img":
            return None
        return self.data.get("s") or self.data.get("src")


class BaseContentProcessor(ABC):
    """Base class for processing content nodes into different formats"""

    def __init__(self, img_dir: Path):
        self.img_dir = img_dir
        self.context = self._init_context()

    @abstractmethod
    def _init_context(self) -> dict[str, Any]:
        """Initialize processor-specific context"""
        pass

    def process_structure(self, structure: list[dict[str, Any]]) -> str:
        """Process the entire document structure"""
        nodes = [ContentNode(item) for item in structure]
        content_parts = []

        for node in nodes:
            processed = self.process_node(node)
            if processed:
                content_parts.append(processed)

        return self._finalize_content(content_parts)

    def process_node(self, node: ContentNode) -> str:
        """Process a single content node"""
        if not node.type:
            return self._escape_text(node.get_text())

        if node.type == "img":
            return self._process_image(node)

        # Process children first
        children_content = self._process_children(node)

        # Apply node-specific processing
        return self._process_node_type(node, children_content)

    def _process_children(self, node: ContentNode) -> str:
        """Process child nodes and text content"""
        if node.is_text_node():
            return self._escape_text(node.get_text())

        parts = []
        if isinstance(node.content, list):
            for item in node.content:
                if isinstance(item, str):
                    parts.append(self._escape_text(item))
                elif isinstance(item, dict):
                    child_node = ContentNode(item)
                    parts.append(self.process_node(child_node))

        return "".join(parts)

    @abstractmethod
    def _process_node_type(self, node: ContentNode, content: str) -> str:
        """Process specific node types - implemented by subclasses"""
        pass

    @abstractmethod
    def _process_image(self, node: ContentNode) -> str:
        """Process image nodes - implemented by subclasses"""
        pass

    @abstractmethod
    def _escape_text(self, text: str) -> str:
        """Escape text for the target format"""
        pass

    @abstractmethod
    def _finalize_content(self, content_parts: list[str]) -> str:
        """Finalize the processed content"""
        pass
