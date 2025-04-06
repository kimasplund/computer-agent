"""
Main entry point for the Computer Agent application.
Initializes the application and launches the UI.
"""
import sys
import argparse
from PyQt6.QtWidgets import QApplication
from .__version__ import __version__
from .window import MainWindow
from .store import Store
from .anthropic import AnthropicClient
from .config import Config
from .logger import initialize_logging, get_logger
from .exceptions import ComputerAgentError

# Initialize logging
initialize_logging()
logger = get_logger("main")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Computer Agent application")
    
    # Add arguments for controlling Wayland behavior
    parser.add_argument("--no-wayland", action="store_true", 
                        help="Disable Wayland-specific features")
    parser.add_argument("--force-x11", action="store_true",
                        help="Force using X11 platform plugin")
    parser.add_argument("--debug-screens", action="store_true",
                        help="Debug screen information")
    parser.add_argument("--scale-factor", type=float, default=0.0,
                        help="Set custom scale factor")
    
    return parser.parse_args()

def main():
    """Main entry point for the application."""
    try:
        logger.info(f"Starting Computer Agent v{__version__}")
        
        # Parse command line arguments
        args = parse_arguments()
        
        # Set platform plugin if requested
        if args.force_x11:
            logger.info("Forcing X11 platform plugin")
            # This must be done before QApplication is created
            import os
            os.environ["QT_QPA_PLATFORM"] = "xcb"
        
        # Create application
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)  # Prevent app from quitting when window is closed
        
        # Initialize configuration
        config = Config()
        logger.info("Configuration initialized")
        
        # Apply command line arguments to configuration
        if args.no_wayland:
            logger.info("Disabling Wayland features via command line argument")
            config.set("wayland", "enabled", "false")
        
        if args.debug_screens:
            logger.info("Enabling screen debugging")
            config.set("wayland", "debug_screen_info", True)
            
        if args.scale_factor > 0:
            logger.info(f"Setting scale factor to {args.scale_factor}")
            config.set("wayland", "force_scale_factor", args.scale_factor)
        
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
