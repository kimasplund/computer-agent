"""
Main entry point for the Computer Agent application.
Initializes the application and launches the UI.
"""
import sys
from PyQt6.QtWidgets import QApplication
from . import __version__
from .window import MainWindow
from .store import Store
from .anthropic import AnthropicClient
from .config import Config
from .logger import initialize_logging, get_logger
from .exceptions import ComputerAgentError

# Initialize logging
initialize_logging()
logger = get_logger("main")

def main():
    """Main entry point for the application."""
    try:
        logger.info(f"Starting Computer Agent v{__version__.__version__}")
        
        # Create application
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)  # Prevent app from quitting when window is closed
        
        # Initialize configuration
        config = Config()
        logger.info("Configuration initialized")
        
        # Initialize components
        try:
            store = Store(config)
            logger.info("Store initialized")
            
            anthropic_client = AnthropicClient(config)
            logger.info("Anthropic client initialized")
            
            # Create and show window
            window = MainWindow(store, anthropic_client, config)
            window.show()
            logger.info("Main window displayed")
            
            # Run application
            return_code = app.exec()
            logger.info(f"Application exited with code {return_code}")
            return return_code
            
        except ComputerAgentError as e:
            logger.error(f"Initialization error: {e}")
            # Show error dialog here if needed
            return 1
            
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
