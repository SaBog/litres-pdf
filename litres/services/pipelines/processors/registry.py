from litres.services.pipelines.base import OutFormat
from .txt import TxtProcessor
from .fb2 import Fb2Processor

PROCESSOR_REGISTRY = {
    OutFormat.TXT: TxtProcessor(),
    OutFormat.FB2: Fb2Processor(),
} 