"""
Custom exceptions for the Computer Agent application.
Provides a centralized and structured approach to error handling.
"""
from typing import Optional


class ComputerAgentError(Exception):
    """Base exception for all Computer Agent errors."""
    
    def __init__(self, message: str = "An error occurred in Computer Agent", 
                 error_code: Optional[str] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class ConfigurationError(ComputerAgentError):
    """Exception raised for configuration-related errors."""
    
    def __init__(self, message: str = "Configuration error", 
                 error_code: Optional[str] = None):
        super().__init__(f"Configuration Error: {message}", error_code)


class APIError(ComputerAgentError):
    """Exception raised for API-related errors."""
    
    def __init__(self, message: str = "API error", 
                 error_code: Optional[str] = None,
                 status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(f"API Error: {message}", error_code)


class AnthropicError(APIError):
    """Exception raised for Anthropic API-related errors."""
    
    def __init__(self, message: str = "Anthropic API error", 
                 error_code: Optional[str] = None,
                 status_code: Optional[int] = None):
        super().__init__(f"Anthropic API Error: {message}", error_code, status_code)


class ComputerControlError(ComputerAgentError):
    """Exception raised for computer control-related errors."""
    
    def __init__(self, message: str = "Computer control error", 
                 error_code: Optional[str] = None,
                 action_type: Optional[str] = None):
        self.action_type = action_type
        super().__init__(
            f"Computer Control Error{'(' + action_type + ')' if action_type else ''}: {message}", 
            error_code
        )


class VoiceControlError(ComputerAgentError):
    """Exception raised for voice control-related errors."""
    
    def __init__(self, message: str = "Voice control error", 
                 error_code: Optional[str] = None):
        super().__init__(f"Voice Control Error: {message}", error_code)


class UIError(ComputerAgentError):
    """Exception raised for UI-related errors."""
    
    def __init__(self, message: str = "UI error", 
                 error_code: Optional[str] = None,
                 component: Optional[str] = None):
        self.component = component
        super().__init__(
            f"UI Error{'(' + component + ')' if component else ''}: {message}", 
            error_code
        )


class StorageError(ComputerAgentError):
    """Exception raised for data storage-related errors."""
    
    def __init__(self, message: str = "Storage error", 
                 error_code: Optional[str] = None,
                 file_path: Optional[str] = None):
        self.file_path = file_path
        super().__init__(
            f"Storage Error{'(' + file_path + ')' if file_path else ''}: {message}", 
            error_code
        )


class InvalidInputError(ComputerAgentError):
    """Exception raised for invalid user input."""
    
    def __init__(self, message: str = "Invalid input", 
                 error_code: Optional[str] = None):
        super().__init__(f"Invalid Input Error: {message}", error_code)


class PermissionError(ComputerAgentError):
    """Exception raised for permission-related errors."""
    
    def __init__(self, message: str = "Permission denied", 
                 error_code: Optional[str] = None,
                 resource: Optional[str] = None):
        self.resource = resource
        super().__init__(
            f"Permission Error{'(' + resource + ')' if resource else ''}: {message}", 
            error_code
        )


class NetworkError(ComputerAgentError):
    """Exception raised for network-related errors."""
    
    def __init__(self, message: str = "Network error", 
                 error_code: Optional[str] = None):
        super().__init__(f"Network Error: {message}", error_code)


class TimeoutError(ComputerAgentError):
    """Exception raised for timeout-related errors."""
    
    def __init__(self, message: str = "Operation timed out", 
                 error_code: Optional[str] = None,
                 operation: Optional[str] = None,
                 timeout_seconds: Optional[float] = None):
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        timeout_info = ""
        if operation:
            timeout_info += f"({operation}"
            if timeout_seconds:
                timeout_info += f", {timeout_seconds}s"
            timeout_info += ")"
        super().__init__(f"Timeout Error{timeout_info}: {message}", error_code)


class ResourceExhaustedError(ComputerAgentError):
    """Exception raised when a resource is exhausted."""
    
    def __init__(self, message: str = "Resource exhausted", 
                 error_code: Optional[str] = None,
                 resource: Optional[str] = None):
        self.resource = resource
        super().__init__(
            f"Resource Exhausted Error{'(' + resource + ')' if resource else ''}: {message}", 
            error_code
        ) 