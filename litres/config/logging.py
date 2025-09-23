import logging
import structlog
import re
from litres.config.settings import app_settings


class PlainFileFormatter(logging.Formatter):
    """Formatter for files that removes ANSI escape codes"""

    def format(self, record):
        # Format the message
        message = super().format(record)
        # Remove ANSI escape codes
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", message)


def setup_logging():
    """Logging setup with clean output to file"""

    handlers = []

    # Console handler with colors
    console_handler = logging.StreamHandler()
    handlers.append(console_handler)

    if app_settings.log_file_name:
        # File handler without colors
        file_handler = logging.FileHandler(
            app_settings.log_file_name,
            encoding="utf-8",
        )
        # Set formatter without colors for file
        file_handler.setFormatter(PlainFileFormatter("%(message)s"))
        handlers.append(file_handler)

    # Basic logging setup
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
        handlers=handlers,
    )

    # Remove unnecessary logs
    logging.getLogger("tqdm").setLevel(logging.WARNING)
    logging.getLogger("fontTools").setLevel(logging.ERROR)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


logger: structlog.stdlib.BoundLogger = structlog.get_logger()
