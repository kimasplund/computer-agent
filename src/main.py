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
from .computer import ComputerControl
from .prompt_manager import PromptManager
import logging

logger = logging.getLogger(__name__)

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
        # Initialize logging first
        initialize_logging()
        logger.info(f"Starting Computer Agent v{__version__}")
        
        # Parse command line arguments
        args = parse_arguments()
        
        # Set platform plugin if requested
        if args.force_x11:
            logger.info("Forcing X11 platform plugin")
            # This must be done before QApplication is created
            import os
            os.environ["QT_QPA_PLATFORM"] = "xcb"
        
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
        
        # Initialize ComputerControl first to get screen information
        computer_control = ComputerControl(config)
        
        # Initialize prompt manager with display information
        prompt_manager = PromptManager()
        
        # Create display information dictionary
        display_info = {
            "screen_width": computer_control.screen_width,
            "screen_height": computer_control.screen_height,
            "is_wayland": computer_control.is_wayland,
            "screen_count": len(computer_control.screens),
            "screens_info": "\n".join([f"- Screen {i+1}: {s['width']}x{s['height']} at position ({s['x']},{s['y']})" 
                                     for i, s in enumerate(computer_control.screens)])
        }
        
        # Set display info in prompt manager
        prompt_manager.set_display_info(display_info)
        
        # Initialize Anthropic client with the prompt manager
        try:
            anthropic_client = AnthropicClient(config=config, prompt_manager=prompt_manager)
            logger.info("Anthropic client initialized")
        except ValueError as e:
            logger.error(f"Failed to initialize Anthropic client: {str(e)}")
            sys.exit(1)
        
        # Initialize store
        store = Store(config=config, computer_control=computer_control, anthropic_client=anthropic_client)
        logger.info("Store initialized")
        
        # Create and show the main window
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)  # Don't quit when main window is closed
        window = MainWindow(store, anthropic_client, config)
        window.show()
        logger.info("Main window displayed")
        
        try:
            return_code = app.exec_()
            logger.info(f"Application exited with code {return_code}")
            return return_code
        except Exception as e:
            logger.error(f"Application error: {str(e)}")
            return 1
            
    except ComputerAgentError as e:
        logger.error(f"Initialization error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
