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

logger = logging.getLogger(__name__)

class AnthropicClient:
    def __init__(self, config=None):
        load_dotenv()  # Load environment variables from .env file
        
        # Use config if provided, otherwise use environment variables
        self.config = config or API_CONFIG
        
        # Get API configuration values
        if config and hasattr(config, 'get'):
            # Using Config class which requires section and key
            self.api_key = config.get("api", "anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
            self.model = config.get("api", "anthropic_model") or "claude-3-5-sonnet-20241022"
            self.max_tokens = config.get("api", "anthropic_max_tokens") or 1024
            
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
            self.prompt_manager = PromptManager()
            logger.info(f"Anthropic client initialized with model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {str(e)}")
            raise ValueError(f"Failed to initialize Anthropic client: {str(e)}")
            
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
        Convert message history to dictionary format expected by the API
        Optionally truncates history to reduce token usage
        """
        cleaned_history = []
        for message in run_history:
            if isinstance(message, BetaMessage):
                # Preserve message ID if present
                msg_dict = {
                    "role": message.role,
                    "content": message.content
                }
                if hasattr(message, 'id'):
                    msg_dict['id'] = message.id
                cleaned_history.append(msg_dict)
            elif isinstance(message, dict) and "role" in message and "content" in message:
                cleaned_history.append(message)
            else:
                raise ValueError(f"Unexpected message type: {type(message)}")
                
        # Only keep essential history if it's getting long and truncation is enabled
        if self.truncate_history and len(cleaned_history) > self.history_truncation_threshold:
            # Keep the first user message (task instruction)
            start_messages = [cleaned_history[0]] if cleaned_history else []
            
            # Calculate how many recent messages to keep (75% of threshold)
            recent_count = max(int(self.history_truncation_threshold * 0.75), 3)
            
            # And the most recent N messages
            recent_messages = cleaned_history[-recent_count:] if len(cleaned_history) >= recent_count else cleaned_history
            
            # Collect IDs of truncated messages for later reference
            truncated_ids = []
            for msg in cleaned_history[1:-recent_count]:
                if isinstance(msg, dict) and 'id' in msg:
                    truncated_ids.append(msg['id'])
            
            # Create a concise summary of the truncated messages to maintain context
            summary = self._create_truncated_message_summary(cleaned_history[1:-recent_count])
            
            # Add a marker to indicate truncation, with reference IDs and summary
            truncation_marker = [{
                "role": "system", 
                "content": [{"type": "text", "text": f"Some conversation history ({len(cleaned_history) - 1 - len(recent_messages)} messages) has been summarized for brevity: {summary} If needed, complete messages can be retrieved from local storage."}]
            }]
            
            if truncated_ids:
                # Log truncated message IDs for potential retrieval
                logger.debug(f"Truncated message IDs: {truncated_ids}")
            
            logger.info(f"Truncated conversation history from {len(cleaned_history)} to {1 + 1 + len(recent_messages)} messages")
            
            # Combine relevant portions
            return start_messages + truncation_marker + recent_messages
            
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
        try:
            # Periodically clean expired cache entries
            self._clean_cache()
            
            # Convert message history to the format expected by the API
            cleaned_history = self._clean_message_history(run_history)
            
            # Check cache for identical conversation, if caching is enabled
            if self.enable_caching:
                # For caching purposes, we only include essential parts of the message
                # to avoid ID fields affecting the hash
                cache_history = []
                for msg in cleaned_history:
                    cache_msg = {
                        'role': msg['role'],
                        'content': msg['content']
                    }
                    cache_history.append(cache_msg)
                
                # Compute a hash of the entire conversation context
                conversation_hash = self._compute_hash([
                    cache_history,
                    self.prompt_manager.get_current_prompt(),
                    self.model,
                    self.max_tokens
                ])
                
                # Check if we have a cached response for this exact conversation
                if conversation_hash in self.message_hash_cache:
                    response_hash, _ = self.message_hash_cache[conversation_hash]
                    if response_hash in self.response_cache:
                        cached_response, _ = self.response_cache[response_hash]
                        logger.info("Using cached response for identical conversation")
                        return cached_response
            
            # Define tools
            tools = [
                {
                    "type": "computer_20241022",
                    "name": "computer",
                    "display_width_px": 1280,
                    "display_height_px": 800,
                    "display_number": 1,
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
            
            # Get system prompt from prompt manager
            system_prompt = self.prompt_manager.get_current_prompt()
            
            # Make API request with enhanced retries for transient errors
            max_retries = 5  # Increased from 3 for better resilience
            base_delay = 2.0  # Base delay in seconds
            max_delay = 30.0  # Maximum delay in seconds
            jitter_factor = 0.25  # Random jitter factor to avoid thundering herd
            
            for attempt in range(max_retries):
                try:
                    # Check if we should apply rate limiting
                    self._apply_rate_limiting()
                    
                    # Log the attempt
                    if attempt > 0:
                        logger.info(f"API request attempt {attempt+1}/{max_retries}")
                    
                    # Make the API call
                    response = self.client.beta.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        tools=tools,
                        messages=cast(List[MessageParam], cleaned_history),
                        system=system_prompt,
                        betas=["computer-use-2024-10-22"],
                    )
                    
                    # Record successful call for rate limiting
                    self._record_api_call()
                    break
                    
                except anthropic.RateLimitError as e:
                    # Calculate backoff with exponential increase and jitter
                    delay = min(max_delay, base_delay * (2 ** attempt))
                    # Add jitter to avoid thundering herd problem
                    jitter = delay * jitter_factor * (2 * (0.5 - time.time() % 1))
                    wait_time = delay + jitter
                    
                    if attempt < max_retries - 1:
                        logger.warning(f"Rate limit hit, retrying in {wait_time:.2f}s... (attempt {attempt+1}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Rate limit exceeded after {max_retries} attempts")
                        raise AnthropicError(f"Rate limit exceeded: {str(e)}", "rate_limit", 429)
                        
                except anthropic.APITimeoutError:
                    # Calculate backoff with exponential increase and jitter
                    delay = min(max_delay, base_delay * (2 ** attempt))
                    jitter = delay * jitter_factor * (2 * (0.5 - time.time() % 1))
                    wait_time = delay + jitter
                    
                    if attempt < max_retries - 1:
                        logger.warning(f"API timeout, retrying in {wait_time:.2f}s... (attempt {attempt+1}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"API request timed out after {max_retries} attempts")
                        raise AnthropicError("API request timed out after multiple attempts", "timeout", 504)
                        
                except anthropic.APIStatusError as e:
                    # Handle specific status codes
                    status_code = getattr(e, "status_code", 0)
                    
                    # 429 is rate limiting, 500s are server errors - both are retryable
                    if status_code == 429 or (status_code >= 500 and status_code < 600):
                        delay = min(max_delay, base_delay * (2 ** attempt))
                        jitter = delay * jitter_factor * (2 * (0.5 - time.time() % 1))
                        wait_time = delay + jitter
                        
                        if attempt < max_retries - 1:
                            logger.warning(f"API error {status_code}, retrying in {wait_time:.2f}s... (attempt {attempt+1}/{max_retries})")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"API error {status_code} persisted after {max_retries} attempts")
                            raise AnthropicError(f"API error: {str(e)}", getattr(e, "error_code", None), status_code)
                    else:
                        # Non-retryable error
                        logger.error(f"Non-retryable API error: {status_code} - {str(e)}")
                        raise AnthropicError(f"API error: {str(e)}", getattr(e, "error_code", None), status_code)
            
            # Handle the case where Claude responds with just text (no tool use)
            has_tool_use = any(isinstance(content, BetaToolUseBlock) for content in response.content)
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
            error_message = f"API Error: {str(e)}"
            logger.error(error_message)
            raise AnthropicError(error_message, getattr(e, "error_code", None), getattr(e, "status_code", None))
        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
            logger.error(error_message)
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
            # Try to use the official API method
            token_count = self.client.count_tokens(text)
            
            # Record successful API call
            self._record_api_call()
            
            # Cache the result if caching is enabled
            if self.enable_caching:
                now = time.time()
                self.token_count_cache[text_hash] = (token_count, now)
                logger.debug(f"Cached token count ({token_count}) for text hash: {text_hash}")
                
            return token_count
            
        except Exception as e:
            logger.warning(f"Token counting API failed: {str(e)}")
            
            # Try different fallback methods with increasing sophistication
            try:
                # Fallback 1: Use tiktoken if available (more accurate than simple word count)
                import tiktoken
                encoding = tiktoken.encoding_for_model(self.model.split('-')[0])
                token_count = len(encoding.encode(text))
                logger.info(f"Used tiktoken fallback for token counting: {token_count} tokens")
                
                # Cache this result too
                if self.enable_caching:
                    now = time.time()
                    self.token_count_cache[text_hash] = (token_count, now)
                    
                return token_count
                
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
