from litres.config import logger
from litres.engines.base import Engine, OutFormat

class O4ToFB2Engine(Engine):
    SUPPORTED_OUT_FORMAT = OutFormat.FB2