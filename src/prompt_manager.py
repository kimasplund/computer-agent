import json
import os
from pathlib import Path
import logging
from .config import DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class PromptManager:
    def __init__(self):
        self.config_dir = Path.home() / ".grunty"
        self.config_file = self.config_dir / "prompts.json"
        self.current_prompt = self.load_prompt()
        self.display_info = {}  # Store display information here

    def load_prompt(self) -> str:
        """Load the system prompt from the config file or return the default"""
        try:
            if not self.config_dir.exists():
                self.config_dir.mkdir(parents=True)
            
            if not self.config_file.exists():
                self.save_prompt(DEFAULT_SYSTEM_PROMPT)
                return DEFAULT_SYSTEM_PROMPT

            with open(self.config_file, 'r') as f:
                data = json.load(f)
                return data.get('system_prompt', DEFAULT_SYSTEM_PROMPT)
        except Exception as e:
            logger.error(f"Error loading prompt: {e}")
            return DEFAULT_SYSTEM_PROMPT

    def save_prompt(self, prompt: str) -> bool:
        """Save the system prompt to the config file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump({'system_prompt': prompt}, f, indent=2)
            self.current_prompt = prompt
            return True
        except Exception as e:
            logger.error(f"Error saving prompt: {e}")
            return False

    def reset_to_default(self) -> bool:
        """Reset the system prompt to the default value"""
        return self.save_prompt(DEFAULT_SYSTEM_PROMPT)

    def get_current_prompt(self) -> str:
        """Get the current system prompt with display information populated"""
        if not self.display_info:
            return self.current_prompt
            
        # Format the prompt with display information if available
        try:
            return self.current_prompt.format(**self.display_info)
        except KeyError as e:
            logger.warning(f"Missing display info key in prompt template: {e}")
            return self.current_prompt
        except Exception as e:
            logger.error(f"Error formatting prompt with display info: {e}")
            return self.current_prompt
            
    def set_display_info(self, display_info: dict) -> None:
        """Set display information to be included in the system prompt
        
        Args:
            display_info: Dictionary with display information such as:
                - screen_width: Width of the primary screen
                - screen_height: Height of the primary screen
                - is_wayland: Whether Wayland is being used
                - screen_count: Number of screens detected
                - screens: List of screen details
        """
        self.display_info = display_info
        logger.info(f"Display information set in prompt manager: {display_info}")
        
    def update_prompt_template(self, new_template: str) -> bool:
        """Update the prompt template while preserving display info"""
        old_display_info = self.display_info
        result = self.save_prompt(new_template)
        self.display_info = old_display_info
        return result
