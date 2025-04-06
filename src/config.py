"""
Configuration module for the Computer Agent application.
Centralizes all configuration parameters in one place.
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base paths
HOME_DIR = Path.home()
CONFIG_DIR = HOME_DIR / ".grunty"
DATA_DIR = CONFIG_DIR / "data"
LOG_DIR = CONFIG_DIR / "logs"

# Create necessary directories
CONFIG_DIR.mkdir(exist_ok=True, parents=True)
DATA_DIR.mkdir(exist_ok=True, parents=True)
LOG_DIR.mkdir(exist_ok=True, parents=True)

# File paths
CONFIG_FILE = CONFIG_DIR / "config.json"
PROMPTS_FILE = CONFIG_DIR / "prompts.json"
LOG_FILE = LOG_DIR / "agent.log"

# API Configuration
API_CONFIG = {
    "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
    "anthropic_model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
    "anthropic_max_tokens": int(os.getenv("ANTHROPIC_MAX_TOKENS", "1024")),
    "enable_caching": os.getenv("ENABLE_CACHING", "true").lower() == "true",
    "cache_ttl": int(os.getenv("CACHE_TTL", "3600")),  # 1 hour default
    "truncate_history": os.getenv("TRUNCATE_HISTORY", "true").lower() == "true",
    "history_truncation_threshold": int(os.getenv("HISTORY_TRUNCATION_THRESHOLD", "10")),
    "compress_screenshots": os.getenv("COMPRESS_SCREENSHOTS", "true").lower() == "true",
    "local_history_enabled": os.getenv("LOCAL_HISTORY_ENABLED", "true").lower() == "true",
    "local_history_max_sessions": int(os.getenv("LOCAL_HISTORY_MAX_SESSIONS", "20")),
    "local_history_cleanup_days": int(os.getenv("LOCAL_HISTORY_CLEANUP_DAYS", "7")),
}

# UI Configuration
UI_CONFIG = {
    "window_width": 400,
    "window_height": 600,
    "min_width": 400,
    "min_height": 500,
    "dark_mode": True,
    "font_family": "Inter",
    "font_size": 14,
    "respect_system_theme": os.getenv("RESPECT_SYSTEM_THEME", "true").lower() == "true",
    "stay_on_top": os.getenv("STAY_ON_TOP", "false").lower() == "true",
}

# Wayland Configuration
WAYLAND_CONFIG = {
    "enabled": os.getenv("WAYLAND_ENABLED", "auto").lower(),  # auto, true, false
    "force_scale_factor": float(os.getenv("QT_SCALE_FACTOR", "0")),  # 0 means auto-detect
    "force_dpi": int(os.getenv("QT_WAYLAND_FORCE_DPI", "0")),  # 0 means auto-detect
    "disable_window_decoration": os.getenv("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1") == "1",
    "maximize_to_active_screen": os.getenv("WAYLAND_MAXIMIZE_TO_ACTIVE", "true").lower() == "true",
    "debug_screen_info": os.getenv("WAYLAND_DEBUG_SCREEN_INFO", "false").lower() == "true",
}

# Voice Configuration
VOICE_CONFIG = {
    "wake_words": ["hey grunty", "hey gruny", "hi grunty", "hi gruny"],
    "speech_rate": 150,
    "use_female_voice": True,
    "timeout": 5,
    "phrase_time_limit": 5,
}

# Computer Control Configuration
COMPUTER_CONFIG = {
    "action_pause": 0.5,  # Pause between actions
    "ai_display_width": 1024,  # Reduced from 1280
    "ai_display_height": 640,  # Reduced from 800
    "screenshot_quality": 70,  # WebP quality (0-100, lower = smaller file)
    "screenshot_use_grayscale": False,  # Whether to use grayscale by default
    "screenshot_use_bw_mode": False,  # Whether to use black and white mode by default
    "screenshot_optimization": "balanced",  # Options: minimal, balanced, aggressive
    "auto_bw_for_text": True,  # Auto-use B&W for text elements like address bars
}

# Default system prompt
DEFAULT_SYSTEM_PROMPT = """The user will ask you to perform a task and you should use their computer to do so. After each step, take a screenshot and carefully evaluate if you have achieved the right outcome. Explicitly show your thinking: 'I have evaluated step X...' If not correct, try again. Only when you confirm a step was executed correctly should you move on to the next one. 

Important screenshot capabilities:
1. You can take focused screenshots of specific regions by specifying 'element_type' in your action:
   - For browser address bars: use element_type='browser_address' (automatically uses B&W mode)
   - For text input fields: use element_type='text_field' (automatically uses B&W mode)
   - For clickable buttons: use element_type='button'
   - For menu interactions: use element_type='menu'
   - For dialog boxes: use element_type='dialog'

2. You can optimize screenshots using these parameters:
   - For grayscale screenshots (smaller size): set grayscale=True
   - For black & white screenshots (smallest size, best for text): set bw_mode=True
   - To skip unnecessary screenshots: set skip_before_screenshot=True or skip_after_screenshot=True
   - For custom regions: set region=(x, y, width, height)

Note that you have to click into the browser address bar before typing a URL. You should always call a tool! Always return a tool call. Remember call the finish_run tool when you have achieved the goal of the task. Do not explain you have finished the task, just call the tool. Use keyboard shortcuts to navigate whenever possible."""

class Config:
    """Configuration manager for the application."""
    
    def __init__(self):
        self._config: Dict[str, Any] = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            else:
                # Create default configuration
                default_config = {
                    "api": API_CONFIG,
                    "ui": UI_CONFIG,
                    "voice": VOICE_CONFIG,
                    "computer": COMPUTER_CONFIG,
                    "wayland": WAYLAND_CONFIG,
                }
                self._save_config(default_config)
                return default_config
        except Exception as e:
            print(f"Error loading configuration: {e}")
            # Return default configuration if loading fails
            return {
                "api": API_CONFIG,
                "ui": UI_CONFIG,
                "voice": VOICE_CONFIG,
                "computer": COMPUTER_CONFIG,
                "wayland": WAYLAND_CONFIG,
            }
    
    def _save_config(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Save configuration to file."""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config or self._config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return False
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        try:
            return self._config.get(section, {}).get(key, default)
        except Exception:
            return default
    
    def set(self, section: str, key: str, value: Any) -> bool:
        """Set a configuration value and save to file."""
        try:
            if section not in self._config:
                self._config[section] = {}
            self._config[section][key] = value
            return self._save_config()
        except Exception as e:
            print(f"Error setting configuration: {e}")
            return False
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get an entire configuration section."""
        return self._config.get(section, {})
    
    def set_section(self, section: str, values: Dict[str, Any]) -> bool:
        """Set an entire configuration section and save to file."""
        try:
            self._config[section] = values
            return self._save_config()
        except Exception as e:
            print(f"Error setting section configuration: {e}")
            return False
    
    def reset_to_default(self) -> bool:
        """Reset configuration to default values."""
        try:
            default_config = {
                "api": API_CONFIG,
                "ui": UI_CONFIG,
                "voice": VOICE_CONFIG,
                "computer": COMPUTER_CONFIG,
                "wayland": WAYLAND_CONFIG,
            }
            self._config = default_config
            return self._save_config()
        except Exception as e:
            print(f"Error resetting configuration: {e}")
            return False
    
    def is_wayland_enabled(self) -> bool:
        """Check if Wayland support is enabled."""
        wayland_setting = self.get("wayland", "enabled", "auto")
        
        if wayland_setting == "true":
            return True
        elif wayland_setting == "false":
            return False
        else:  # auto detection
            # Check for Wayland environment variables
            return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or \
                   os.environ.get("WAYLAND_DISPLAY", "") != ""
    
    def get_wayland_scale_factor(self) -> float:
        """Get the configured Wayland scale factor."""
        # Check for forced scale factor
        scale_factor = self.get("wayland", "force_scale_factor", 0)
        if scale_factor > 0:
            return scale_factor
            
        # Check environment variable
        qt_scale = os.environ.get("QT_SCALE_FACTOR")
        if qt_scale and qt_scale.replace('.', '', 1).isdigit():
            return float(qt_scale)
            
        # Default to 1.0 (no scaling)
        return 1.0 