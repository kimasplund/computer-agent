import anthropic
from anthropic.types.beta import BetaMessage, BetaTextBlock, BetaToolUseBlock
from anthropic.types import MessageParam
import os
import time
import hashlib
from typing import List, Dict, Any, Union, Optional, cast, Tuple
from dotenv import load_dotenv
import logging
from .prompt_manager import PromptManager
from .exceptions import AnthropicError
from .config import API_CONFIG
import random
import json
import uuid

logger = logging.getLogger(__name__)

class AnthropicClient:
    def __init__(self, config=None, prompt_manager=None):
        load_dotenv()  # Load environment variables from .env file
        
        # Use config if provided, otherwise use environment variables
        self.config = config or API_CONFIG
        
        # Development mode flags
        self.use_mock_api = os.getenv("USE_MOCK_API", "false").lower() == "true"
        if self.use_mock_api:
            logger.warning("USING MOCK ANTHROPIC API FOR DEVELOPMENT/TESTING")
        
        # Get API configuration values
        if config and hasattr(config, 'get'):
            # Using Config class which requires section and key
            self.api_key = config.get("api", "anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
            self.model = config.get("api", "anthropic_model") or "claude-3-5-sonnet-20241022"
            self.max_tokens = config.get("api", "anthropic_max_tokens") or 1024
            
            # Check for mock API mode in config
            if not self.use_mock_api and config.get("api", "use_mock_api", False):
                self.use_mock_api = True
                logger.warning("USING MOCK ANTHROPIC API (from config) FOR DEVELOPMENT/TESTING")
            
            # Cache and optimization configuration
            self.cache_ttl = config.get('api', 'cache_ttl', 3600)
            self.enable_caching = config.get('api', 'enable_caching', True)
            self.truncate_history = config.get('api', 'truncate_history', True)
            self.history_truncation_threshold = config.get('api', 'history_truncation_threshold', 10)
            self.rate_limit_window = config.get('api', 'rate_limit_window', 60.0)
            self.max_calls_per_minute = config.get('api', 'max_calls_per_minute', 20)
        else:
            # Using API_CONFIG dictionary
            self.api_key = API_CONFIG.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
            self.model = API_CONFIG.get("anthropic_model") or "claude-3-5-sonnet-20241022"
            self.max_tokens = API_CONFIG.get("anthropic_max_tokens") or 1024
            
            # Get settings from API_CONFIG with defaults
            self.cache_ttl = API_CONFIG.get('cache_ttl', 3600)  # Cache lifetime in seconds (1 hour)
            self.enable_caching = API_CONFIG.get('enable_caching', True)  # Whether to use the cache
            self.truncate_history = API_CONFIG.get('truncate_history', True)  # Whether to truncate long conversation history
            self.history_truncation_threshold = API_CONFIG.get('history_truncation_threshold', 10)  # Message count threshold
            self.rate_limit_window = API_CONFIG.get('rate_limit_window', 60.0)  # Window in seconds for rate limiting
            self.max_calls_per_minute = API_CONFIG.get('max_calls_per_minute', 20)  # Maximum calls per minute
        
        # Initialize token caches
        self.token_count_cache: Dict[str, Tuple[int, float]] = {}  # Maps text hash to (token_count, timestamp)
        self.message_hash_cache: Dict[str, Tuple[str, float]] = {}  # Maps message hash to (response_hash, timestamp)
        self.response_cache: Dict[str, Tuple[BetaMessage, float]] = {}  # Maps response hash to (response, timestamp)
        
        # Rate limiting configuration
        self.api_calls: List[float] = []  # Timestamps of recent API calls
        
        logger.info(f"Token caching {'enabled' if self.enable_caching else 'disabled'} (TTL: {self.cache_ttl}s)")
        logger.info(f"Rate limiting: {self.max_calls_per_minute} calls per {self.rate_limit_window}s")
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables or config")
        
        try:
            # Initialize with timeout and default headers for better reliability
            self.client = anthropic.Anthropic(
                api_key=self.api_key,
                timeout=60.0,  # 60 second timeout for API calls
            )
            # Use provided prompt manager or create a new one
            self.prompt_manager = prompt_manager or PromptManager()
            logger.info(f"Anthropic client initialized with model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {str(e)}")
            raise ValueError(f"Failed to initialize Anthropic client: {str(e)}")
            
    def _get_computer_tool_definition(self):
        """
        Get the computer tool definition with the correct screen dimensions from display_info
        """
        # Default values in case display_info isn't available
        display_width = 1280
        display_height = 800
        display_number = 1
        
        # Use display_info from prompt_manager if available
        if hasattr(self, 'prompt_manager') and hasattr(self.prompt_manager, 'display_info'):
            display_info = self.prompt_manager.display_info
            if display_info:
                # Extract screen dimensions from display_info
                display_width = display_info.get('screen_width', display_width)
                display_height = display_info.get('screen_height', display_height)
                display_number = display_info.get('screen_count', display_number)
                
                logger.info(f"Using dynamic screen dimensions: {display_width}x{display_height} with {display_number} displays")
        
        return [
            {
                "type": "computer_20241022",
                "name": "computer",
                "display_width_px": display_width,
                "display_height_px": display_height,
                "display_number": display_number,
            },
            {
                "name": "finish_run",
                "description": "Call this function when you have achieved the goal of the task.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "Whether the task was successful"
                        },
                        "error": {
                            "type": "string",
                            "description": "The error message if the task was not successful"
                        }
                    },
                    "required": ["success"]
                }
            }
        ]
            
    def _apply_rate_limiting(self) -> None:
        """
        Apply rate limiting to prevent exceeding API rate limits.
        This method will pause execution if we're making too many calls too quickly.
        """
        now = time.time()
        
        # Clean up old timestamps outside the window
        self.api_calls = [ts for ts in self.api_calls if now - ts < self.rate_limit_window]
        
        # Check if we're at the rate limit
        if len(self.api_calls) >= self.max_calls_per_minute:
            # Calculate how long to wait
            oldest_call = min(self.api_calls)
            wait_time = self.rate_limit_window - (now - oldest_call) + 0.1  # Add a small buffer
            
            if wait_time > 0:
                logger.warning(f"Rate limit approaching, pausing for {wait_time:.2f}s")
                time.sleep(wait_time)
                
    def _record_api_call(self) -> None:
        """
        Record a successful API call for rate limiting purposes
        """
        self.api_calls.append(time.time())
    
    def _clean_message_history(self, run_history: List[Union[BetaMessage, Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Convert message history to dictionary format expected by the API.
        Ensures proper pairing of tool_use and tool_result blocks to avoid API errors.
        """
        cleaned_history = []
        tool_use_ids = set()  # Track tool_use IDs that need tool_result blocks
        
        # First pass: convert messages and track tool_use IDs
        for message in run_history:
            if isinstance(message, BetaMessage):
                msg_dict = {
                    "role": message.role,
                    "content": message.content
                }
                cleaned_history.append(msg_dict)
                
                # Track tool_use IDs to ensure proper pairing
                if message.role == "assistant":
                    for block in message.content:
                        if hasattr(block, 'type') and block.type == 'tool_use' and hasattr(block, 'id'):
                            tool_use_ids.add(block.id)
            elif isinstance(message, dict) and "role" in message and "content" in message:
                # Create a new dict without the 'id' field if present
                msg_dict = {
                    "role": message["role"],
                    "content": message["content"]
                }
                cleaned_history.append(msg_dict)
                
                # Track tool_use IDs to ensure proper pairing
                if message["role"] == "assistant" and isinstance(message["content"], list):
                    for block in message["content"]:
                        if isinstance(block, dict) and block.get("type") == "tool_use" and "id" in block:
                            tool_use_ids.add(block["id"])
            else:
                raise ValueError(f"Unexpected message type: {type(message)}")
        
        # Second pass: analyze to ensure each tool_use has a matching tool_result
        # This is critical to avoid the API error about missing tool_result blocks
        result_blocks_by_tool_id = {}
        
        # Find all tool_result blocks
        for msg in cleaned_history:
            if msg["role"] == "user" and isinstance(msg["content"], list):
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result" and "tool_use_id" in block:
                        result_blocks_by_tool_id[block["tool_use_id"]] = True
        
        # Check if any tool_use blocks don't have corresponding tool_result blocks
        missing_result_ids = tool_use_ids - set(result_blocks_by_tool_id.keys())
        
        if missing_result_ids:
            logger.warning(f"Found {len(missing_result_ids)} tool_use blocks without matching tool_result blocks")
            logger.warning(f"Will filter out problematic messages to avoid API errors")
            
            # Get indexes of messages with problematic tool_use blocks
            problem_indexes = []
            for i, msg in enumerate(cleaned_history):
                if msg["role"] == "assistant" and isinstance(msg["content"], list):
                    has_problem = False
                    for block in msg["content"]:
                        if isinstance(block, dict) and block.get("type") == "tool_use" and "id" in block:
                            if block["id"] in missing_result_ids:
                                has_problem = True
                                break
                    if has_problem:
                        problem_indexes.append(i)
            
            # If we found problematic messages, remove them and their missing tool_result pairs
            if problem_indexes:
                logger.warning(f"Removing {len(problem_indexes)} problematic messages to avoid API errors")
                # Create a new history without the problematic messages
                cleaned_history = [msg for i, msg in enumerate(cleaned_history) if i not in problem_indexes]
        
        # Ensure we have at least one message in history
        if not cleaned_history:
            # Create a basic system prompt
            cleaned_history.append({
                "role": "system", 
                "content": "You are Claude, an AI assistant that can control computer devices. Help the user with their requests."
            })
        
        return cleaned_history
        
    def _create_truncated_message_summary(self, messages: List[Dict[str, Any]]) -> str:
        """
        Create a brief summary of truncated messages to maintain context
        
        Args:
            messages: List of messages being truncated
            
        Returns:
            A concise summary string
        """
        if not messages:
            return ""
            
        # Count screenshots and text messages
        screenshot_count = 0
        text_messages = []
        actions = set()
        
        for msg in messages:
            if isinstance(msg, dict) and 'content' in msg:
                # Check for screenshots
                if isinstance(msg['content'], list):
                    for item in msg['content']:
                        if isinstance(item, dict) and item.get('type') == 'tool_result':
                            for content_item in item.get('content', []):
                                if isinstance(content_item, dict) and content_item.get('type') == 'image':
                                    screenshot_count += 1
                
                # Extract text content
                if isinstance(msg['content'], list):
                    for item in msg['content']:
                        if isinstance(item, dict) and item.get('type') == 'text' and 'text' in item:
                            text = item['text'].strip()
                            if text and len(text) > 5:  # Skip very short or empty messages
                                text_messages.append(text)
                                
                # Track action types
                if isinstance(msg, dict) and 'metadata' in msg and 'action_type' in msg['metadata']:
                    actions.add(msg['metadata']['action_type'])
        
        # Create a summary string
        summary_parts = []
        
        # Add screenshot count
        if screenshot_count > 0:
            summary_parts.append(f"{screenshot_count} screenshots")
            
        # Add action summary
        if actions:
            action_str = ", ".join(sorted(actions))
            summary_parts.append(f"Actions: {action_str}")
            
        # Add very brief content summary if available
        if text_messages:
            # Take the first few characters of the first and last text messages
            if len(text_messages) == 1:
                text_preview = text_messages[0][:30] + "..." if len(text_messages[0]) > 30 else text_messages[0]
                summary_parts.append(f"Message: \"{text_preview}\"")
            else:
                summary_parts.append(f"{len(text_messages)} text messages")
                
        # Join the summary parts
        return "; ".join(summary_parts)
    
    def _compute_hash(self, data: Any) -> str:
        """Compute a hash for the given data for caching purposes"""
        if isinstance(data, list):
            # For lists like message history, serialize and hash each item
            serialized = []
            for item in data:
                if isinstance(item, dict):
                    # Sort keys to ensure consistent hashing
                    sorted_item = {k: item[k] for k in sorted(item.keys())}
                    serialized.append(str(sorted_item))
                else:
                    serialized.append(str(item))
            data_str = "||".join(serialized)
        else:
            data_str = str(data)
            
        return hashlib.md5(data_str.encode('utf-8')).hexdigest()
        
    def _clean_cache(self):
        """Remove expired items from caches"""
        now = time.time()
        
        # Clean token count cache
        expired_keys = [k for k, (_, ts) in self.token_count_cache.items() if now - ts > self.cache_ttl]
        for k in expired_keys:
            del self.token_count_cache[k]
            
        # Clean message hash cache
        expired_keys = [k for k, (_, ts) in self.message_hash_cache.items() if now - ts > self.cache_ttl]
        for k in expired_keys:
            del self.message_hash_cache[k]
            
        # Clean response cache
        expired_keys = [k for k, (_, ts) in self.response_cache.items() if now - ts > self.cache_ttl]
        for k in expired_keys:
            del self.response_cache[k]
    
    def get_next_action(self, run_history: List[Union[BetaMessage, Dict[str, Any]]]) -> BetaMessage:
        """
        Get the next action from Claude based on conversation history.
        
        Args:
            run_history: List of conversation messages
            
        Returns:
            BetaMessage: Claude's response with tool use actions
            
        Raises:
            AnthropicError: For API-related errors
            ValueError: For input validation errors
            
        Note:
            If history truncation is enabled, only a subset of the full history will be sent to the API.
            The complete history is stored locally and can be accessed if needed.
        """
        # Check if mock API is enabled (highest priority)
        if self.use_mock_api:
            logger.info("Using mock API instead of calling Anthropic API")
            return self._generate_mock_response(run_history)
        
        try:
            # Validate input
            if not run_history:
                raise ValueError("Empty run history provided")
            
            # Clean and prepare history for API call
            cleaned_history = self._clean_message_history(run_history)
            
            # Compute a hash of the conversation for cache lookup
            conversation_hash = self._compute_hash(cleaned_history)
            
            # Check cache if enabled
            if self.enable_caching and conversation_hash in self.message_hash_cache:
                # Get the cached response hash
                response_hash, timestamp = self.message_hash_cache[conversation_hash]
                
                # Check if the cache entry is still valid
                now = time.time()
                if now - timestamp <= self.cache_ttl and response_hash in self.response_cache:
                    # Get the cached response
                    response, _ = self.response_cache[response_hash]
                    logger.info(f"Using cached response for conversation (hash: {conversation_hash})")
                    return response
            
            # Apply rate limiting for API calls
            self._apply_rate_limiting()
            
            # Make API call with retries for transient errors
            max_retries = 3
            retry_delay = 1.0  # Initial delay in seconds
            error_msg = None
            status_code = None
            
            # Get the system prompt from prompt manager with display info
            system_prompt = self.prompt_manager.get_current_prompt()
            logger.debug(f"Using system prompt with display info: {system_prompt[:100]}...")
            
            for attempt in range(max_retries):
                try:
                    # Make the API call
                    logger.debug(f"Sending request to Anthropic API (attempt {attempt+1}/{max_retries})")
                    
                    response = self.client.beta.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        messages=cleaned_history,
                        tools=self._get_computer_tool_definition(),
                        system=system_prompt,  # Use the system prompt with display info
                        betas=["computer-use-2024-10-22"],
                    )
                    
                    # Record successful API call
                    self._record_api_call()
                    
                    # Check if there's at least one tool use block
                    has_tool_use = False
                    for content in response.content:
                        if isinstance(content, BetaToolUseBlock):
                            has_tool_use = True
                            break
                    
                    if not has_tool_use:
                        text_content = next((content.text for content in response.content if isinstance(content, BetaTextBlock)), "")
                        # Create a synthetic tool use block for finish_run
                        response.content.append(BetaToolUseBlock(
                            id="synthetic_finish",
                            type="tool_use",
                            name="finish_run",
                            input={
                                "success": False,
                                "error": f"Claude needs more information: {text_content}"
                            }
                        ))
                        logger.info(f"Added synthetic finish_run for text-only response: {text_content}")
                    
                    # Store response in cache if caching is enabled
                    if self.enable_caching:
                        # Compute a hash for the response
                        response_hash = self._compute_hash(response)
                        
                        # Store the response in the cache
                        now = time.time()
                        self.response_cache[response_hash] = (response, now)
                        
                        # Map the conversation hash to the response hash
                        self.message_hash_cache[conversation_hash] = (response_hash, now)
                        
                        logger.debug(f"Cached response (hash: {response_hash}) for conversation (hash: {conversation_hash})")

                    return response
                    
                except anthropic.APIError as e:
                    error_msg = f"API Error: Anthropic API Error: API error: {str(e)}"
                    logger.error(error_msg)
                    status_code = getattr(e, "status_code", None)
                    
                    # Check if error is retryable
                    if hasattr(e, "status_code") and e.status_code in (429, 500, 502, 503, 504):
                        # Retryable error - use exponential backoff
                        retry_delay *= (2 + random.random())  # Add jitter
                        logger.warning(f"Retryable API error: {str(e)}. Retrying in {retry_delay:.2f}s")
                        time.sleep(retry_delay)
                        continue
                    else:
                        # Non-retryable error
                        logger.error(f"Non-retryable API error: {status_code} - {str(e)}")
                        break
                
                except Exception as e:
                    error_msg = f"Unexpected error: {str(e)}"
                    logger.error(error_msg)
                    break
            
            # If we get here, all retries failed or we had a non-retryable error
            if self.use_mock_api or os.getenv("USE_MOCK_API", "").lower() == "true":
                # Fallback to mock API if API call fails and mock is allowed
                logger.warning("API call failed, falling back to mock API mode")
                return self._generate_mock_response(run_history)
            
            # Otherwise raise the error
            raise AnthropicError(f"API error: {str(error_msg)}", None, status_code)
            
        except AnthropicError as e:
            # Re-raise Anthropic errors
            error_message = f"Anthropic API Error: {str(e)}"
            logger.error(error_message)
            
            # If mock API is allowed as fallback, use it
            if os.getenv("FALLBACK_TO_MOCK_ON_ERROR", "").lower() == "true":
                logger.warning("API error occurred, falling back to mock API")
                return self._generate_mock_response(run_history)
            
            raise Exception(error_message)
        except Exception as e:
            # Handle other errors
            error_message = f"Unexpected error: {str(e)}"
            logger.error(error_message)
            
            # If mock API is allowed as fallback, use it
            if os.getenv("FALLBACK_TO_MOCK_ON_ERROR", "").lower() == "true":
                logger.warning("Error occurred, falling back to mock API")
                return self._generate_mock_response(run_history)
            
            raise Exception(error_message)
    
    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text string with improved fallback mechanisms.
        
        Args:
            text: The text to count tokens for
            
        Returns:
            int: Token count
        """
        # Check cache first if caching is enabled
        if self.enable_caching:
            text_hash = self._compute_hash(text)
            if text_hash in self.token_count_cache:
                token_count, _ = self.token_count_cache[text_hash]
                logger.debug(f"Using cached token count ({token_count}) for text hash: {text_hash}")
                return token_count
        
        # Apply rate limiting for API calls
        self._apply_rate_limiting()
        
        try:
            # Use the appropriate token counting method based on library version
            try:
                # New method in Anthropic SDK
                if hasattr(self.client, 'messages') and hasattr(self.client.messages, 'count_tokens'):
                    # Create proper message content format for counting
                    message_content = {"role": "user", "content": text}
                    token_count = self.client.messages.count_tokens(
                        messages=[message_content],
                        model=self.model
                    )
                    # Handle different response types
                    if hasattr(token_count, 'usage') and hasattr(token_count.usage, 'input_tokens'):
                        token_count = token_count.usage.input_tokens
                    elif hasattr(token_count, 'input_tokens'):
                        token_count = token_count.input_tokens
                    # Ensure we have an integer
                    token_count = int(token_count) if hasattr(token_count, '__int__') else token_count
                elif hasattr(self.client.beta, 'messages') and hasattr(self.client.beta.messages, 'count_tokens'):
                    # Try beta API with proper message format
                    message_content = {"role": "user", "content": text}
                    token_count = self.client.beta.messages.count_tokens(
                        messages=[message_content],
                        model=self.model
                    )
                    # Handle different response types
                    if hasattr(token_count, 'usage') and hasattr(token_count.usage, 'input_tokens'):
                        token_count = token_count.usage.input_tokens
                    elif hasattr(token_count, 'input_tokens'):
                        token_count = token_count.input_tokens
                    # Ensure we have an integer
                    token_count = int(token_count) if hasattr(token_count, '__int__') else token_count
                elif hasattr(self.client, 'count_tokens'):
                    # Legacy method
                    token_count = self.client.count_tokens(text)
                else:
                    raise ValueError("No valid token counting method found in Anthropic client")
                
                # Record successful API call
                self._record_api_call()
                
                # Cache the result if caching is enabled
                if self.enable_caching:
                    now = time.time()
                    self.token_count_cache[text_hash] = (token_count, now)
                    logger.debug(f"Cached token count ({token_count}) for text hash: {text_hash}")
                    
                return token_count
            except (AttributeError, TypeError) as api_err:
                logger.warning(f"Token counting API method not found: {str(api_err)}")
                raise ValueError("API token counting failed")
                
        except Exception as e:
            logger.warning(f"Token counting API failed: {str(e)}")
            
            # Skip further API attempts if it's an authentication or credit issue
            if "credit balance is too low" in str(e) or "authentication" in str(e).lower():
                logger.warning("API access issue detected, using fallback methods directly")
            
            # Try different fallback methods with increasing sophistication
            try:
                # Fallback 1: Use tiktoken if available (more accurate than simple word count)
                import tiktoken
                
                # Try specific encodings known to work well with Claude
                encoding = None
                try:
                    # For Claude, cl100k_base works well (same as GPT-4)
                    encoding = tiktoken.get_encoding("cl100k_base")
                except:
                    try:
                        # Fallback to p50k_base (GPT-3)
                        encoding = tiktoken.get_encoding("p50k_base")
                    except:
                        # Last resort, try the most basic encoding
                        encoding = tiktoken.get_encoding("gpt2")
                
                if encoding:
                    token_count = len(encoding.encode(text))
                    logger.info(f"Used tiktoken fallback for token counting with {encoding.name}: {token_count} tokens")
                    
                    # Cache this result too
                    if self.enable_caching:
                        now = time.time()
                        self.token_count_cache[text_hash] = (token_count, now)
                        
                    return token_count
                else:
                    raise ValueError("Failed to get tiktoken encoding")
                
            except ImportError:
                logger.warning("Tiktoken not available for token counting fallback")
                
            except Exception as tiktoken_error:
                logger.warning(f"Tiktoken fallback failed: {str(tiktoken_error)}")
            
            # Fallback 2: Use a more sophisticated approximation based on character count
            # Claude models typically use ~4 characters per token on average
            char_count = len(text)
            
            # Adjust for different languages and special characters
            # ASCII characters are typically 1 token per 4 chars
            # Non-ASCII can be 1 token per 1-2 chars
            ascii_count = sum(1 for c in text if ord(c) < 128)
            non_ascii_count = char_count - ascii_count
            
            # Calculate weighted token count
            ascii_tokens = ascii_count / 4.0
            non_ascii_tokens = non_ascii_count / 1.5  # Non-ASCII chars use more tokens
            
            # Add a small overhead for tokenization boundaries
            token_count = int(ascii_tokens + non_ascii_tokens + 5)
            
            logger.info(f"Used character-based fallback for token counting: {token_count} tokens")
            return token_count

    def _generate_mock_response(self, run_history: List[Union[BetaMessage, Dict[str, Any]]]) -> BetaMessage:
        """
        Generate a mock response for development/testing when API is unavailable.
        
        Args:
            run_history: List of conversation messages
            
        Returns:
            BetaMessage: A simulated Claude response
        """
        logger.info("Generating mock response for development/testing")
        
        # Create a mock message ID
        mock_id = f"msg_{int(time.time())}_{hash(str(run_history[-1]))}"
        
        # Extract the last user message to understand what they're asking for
        last_user_message = None
        for msg in reversed(run_history):
            if isinstance(msg, dict) and msg.get('role') == 'user':
                last_user_message = msg
                break
            elif hasattr(msg, 'role') and msg.role == 'user':
                last_user_message = msg
                break
        
        # Default mock action (finish_run) for when we don't recognize the command
        mock_action = {
            "name": "finish_run",
            "input": {
                "success": True,
                "error": None
            }
        }
        
        # Simple keyword matching for common actions
        user_content = ""
        if last_user_message:
            if isinstance(last_user_message, dict) and isinstance(last_user_message.get('content'), list):
                for item in last_user_message['content']:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        user_content += item.get('text', '')
            elif isinstance(last_user_message, dict) and isinstance(last_user_message.get('content'), str):
                user_content = last_user_message['content']
            elif hasattr(last_user_message, 'content'):
                for item in last_user_message.content:
                    if hasattr(item, 'type') and item.type == 'text':
                        user_content += item.text
        
        # Mock different responses based on user content
        if any(term in user_content.lower() for term in ['screenshot', 'screen', 'capture']):
            mock_action = {
                "name": "computer",
                "input": {
                    "action_type": "screenshot",
                    "grayscale": False,
                    "bw_mode": False
                }
            }
            mock_text = "I'll take a screenshot of the current screen."
        elif any(term in user_content.lower() for term in ['click', 'press', 'select']):
            # Mock a click action
            mock_action = {
                "name": "computer",
                "input": {
                    "action_type": "mouse_click",
                    "x": 500,  # Center of screen typically
                    "y": 400
                }
            }
            mock_text = "I'll click at position (500, 400) on the screen."
        elif any(term in user_content.lower() for term in ['type', 'write', 'input']):
            # Mock a keyboard input action
            mock_action = {
                "name": "computer",
                "input": {
                    "action_type": "keyboard_type",
                    "text": "Hello, this is a mock input"
                }
            }
            mock_text = "I'll type the requested text."
        else:
            # Generic response when we don't understand
            mock_text = "I understand your request, but I'm currently in development mode. This is a mock response."
        
        # Create a BetaMessage object for the response
        # First prepare the content items
        content = [
            BetaTextBlock(
                type="text",
                text=mock_text
            ),
            BetaToolUseBlock(
                type="tool_use",
                id=f"tool_{int(time.time())}",
                name=mock_action["name"],
                input=mock_action["input"]
            )
        ]
        
        # Create the message
        return BetaMessage(
            id=mock_id,
            type="message",
            role="assistant",
            model=self.model,
            content=content,
            usage={
                "input_tokens": 0,
                "output_tokens": 0
            }
        )
