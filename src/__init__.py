"""
Computer Agent package initialization.
Exposes version information and main package components.
"""
from .__version__ import __version__, __author__, __author_email__, __description__, __url__

# Import main components to make them available at the package level
from .config import Config
from .store import Store
from .anthropic import AnthropicClient
from .window import MainWindow
from .computer import ComputerControl
from .voice_control import VoiceController
from .prompt_manager import PromptManager
