import sys
from enum import IntEnum

from litres.book_processor import BookProcessor
from litres.config import app_settings, logger, setup_logging
from litres.exceptions import BookProcessingError
from litres.services.auth_service import AuthService


class ExitCode(IntEnum):
    SUCCESS = 0
    AUTH_FAILED = 1
    APP_ERROR = 2

def show_banner():
    print(r"""
██╗     ██╗████████╗██████╗ ███████╗██████╗ ███████╗
██║     ██║╚══██╔══╝██╔══██╗██╔════╝██╔══██╗██╔════╝
██║     ██║   ██║   ██████╔╝█████╗  ██████╔╝███████╗
██║     ██║   ██║   ██╔═══╝ ██╔══╝  ██╔══██╗╚════██║
███████╗██║   ██║   ██║     ███████╗██║  ██║███████║
╚══════╝╚═╝   ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝╚══════╝

LitRes Book Downloader
Bypasses subscription wall and merges pages
    """)

def run_app() -> ExitCode:
    """Main application loop."""
    logger.info("Application started")
    logger.info(f"Current App Settings: {app_settings.model_dump(mode="json")}")

    auth_service = AuthService()
    if not auth_service.authenticate():
        logger.error("Authentication failed. Please check your credentials or network connection.")
        return ExitCode.AUTH_FAILED
    
    book_processor = BookProcessor(auth_service.session)

    while True:
        try:
            url = input("Enter book URL or press Enter to exit: ").strip()
            if not url:
                logger.info("Exiting program")
                return ExitCode.SUCCESS
            
            book_processor.process_book(url)

        except BookProcessingError as e:
            logger.error(f"Failed to process book: {e}", exc_info=False)
        except KeyboardInterrupt:
            logger.info("Application stopped by user")
            return ExitCode.SUCCESS
        except Exception as e:
            logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
    
def main() -> None:
    """Entry point"""
    setup_logging()
    show_banner()
    sys.exit(run_app())

if __name__ == "__main__":
    main()