import logging
from typing import List, Dict, Any, Optional, Union, Callable
import json
import time
import os
import pickle
from pathlib import Path
import datetime

from .anthropic import AnthropicClient
from .computer import ComputerControl
from .exceptions import AnthropicError, ComputerAgentError, StorageError
from anthropic.types.beta import BetaMessage, BetaToolUseBlock, BetaTextBlock
from .config import DATA_DIR

logger = logging.getLogger(__name__)

class Store:
    def __init__(self, config=None):
        """
        Initialize the application store with Anthropic client and Computer control
        
        Args:
            config: Optional configuration object
        """
        self.instructions = ""
        self.fully_auto = True
        self.running = False
        self.error = None
        self.run_history: List[Union[BetaMessage, Dict[str, Any]]] = []
        self.last_tool_use_id = None
        self.last_action = None  # Track the last action for better region selection
        self.config = config
        
        # Session identifier for log files
        self.session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Paths for local history storage
        self.history_dir = DATA_DIR / "history"
        self.history_dir.mkdir(exist_ok=True, parents=True)
        self.history_file = self.history_dir / f"session_{self.session_id}_history.pkl"
        self.history_index_file = self.history_dir / f"session_{self.session_id}_index.json"
        
        # Create index for retrieving historical messages
        self.history_index: Dict[str, Dict[str, Any]] = {}
        
        try:
            self.anthropic_client = AnthropicClient(config)
        except ValueError as e:
            self.error = str(e)
            logger.error(f"AnthropicClient initialization error: {self.error}")
        
        try:
            self.computer_control = ComputerControl(config)
        except Exception as e:
            self.error = str(e)
            logger.error(f"ComputerControl initialization error: {self.error}")
        
    def set_instructions(self, instructions: str) -> None:
        """Set the instructions for the agent run"""
        self.instructions = instructions
        logger.info(f"Instructions set: {instructions}")
        
        # Get token count for instructions
        try:
            token_count = self.anthropic_client.count_tokens(instructions)
            logger.info(f"Instruction token count: {token_count}")
        except Exception:
            # Non-critical, so just log the error
            logger.warning("Unable to count tokens for instructions")
        
    def _save_history_to_disk(self) -> None:
        """
        Save the full conversation history to disk for later retrieval
        """
        try:
            # Calculate total token usage for this session
            try:
                total_tokens = 0
                for msg in self.run_history:
                    # Generate a string representation of the message for token counting
                    if isinstance(msg, dict) and 'content' in msg:
                        content_str = self._message_to_string(msg)
                        if hasattr(self, 'anthropic_client') and self.anthropic_client:
                            tokens = self.anthropic_client.count_tokens(content_str)
                            total_tokens += tokens
            except Exception as e:
                logger.warning(f"Could not calculate token usage: {str(e)}")
                total_tokens = None
            
            # Save the full history as a pickle file
            with open(self.history_file, 'wb') as f:
                pickle.dump(self.run_history, f)
                
            # Update the index with metadata about this history snapshot
            timestamp = datetime.datetime.now().isoformat()
            index_entry = {
                'timestamp': timestamp,
                'message_count': len(self.run_history),
                'file_path': str(self.history_file),
                'estimated_tokens': total_tokens,
                'instruction': self.instructions[:100] + '...' if len(self.instructions) > 100 else self.instructions
            }
            
            # Use timestamp as key for this history snapshot
            self.history_index[timestamp] = index_entry
            
            # Save the updated index
            with open(self.history_index_file, 'w') as f:
                json.dump(self.history_index, f, indent=2)
                
            logger.debug(f"Saved history snapshot with {len(self.run_history)} messages (~{total_tokens} tokens)")
            
        except Exception as e:
            logger.error(f"Failed to save history to disk: {str(e)}")
            
    def _message_to_string(self, message) -> str:
        """Convert a message to a string representation for token counting"""
        if isinstance(message, str):
            return message
            
        if isinstance(message, dict):
            if 'content' not in message:
                return json.dumps(message)
                
            # Handle structured content
            if isinstance(message['content'], list):
                parts = []
                for item in message['content']:
                    if isinstance(item, dict):
                        # Skip image data to avoid massive strings
                        if item.get('type') == 'image' and 'source' in item and 'data' in item['source']:
                            parts.append("[IMAGE DATA]")
                        else:
                            # Extract text if available
                            if 'text' in item:
                                parts.append(item['text'])
                            else:
                                parts.append(json.dumps(item))
                    else:
                        parts.append(str(item))
                return ' '.join(parts)
            else:
                return str(message['content'])
                
        return str(message)
    
    def retrieve_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific message from the history by its ID
        
        Args:
            message_id: The ID of the message to retrieve
            
        Returns:
            The message if found, None otherwise
        """
        # First check the in-memory history
        for msg in self.run_history:
            if isinstance(msg, dict) and msg.get('id') == message_id:
                return msg
                
            if isinstance(msg, BetaMessage) and msg.id == message_id:
                # Convert to dict for consistency
                return {
                    'role': msg.role,
                    'content': msg.content,
                    'id': msg.id
                }
        
        # If not found, check the on-disk history
        try:
            with open(self.history_file, 'rb') as f:
                full_history = pickle.load(f)
                
            for msg in full_history:
                if isinstance(msg, dict) and msg.get('id') == message_id:
                    return msg
                    
                if isinstance(msg, BetaMessage) and msg.id == message_id:
                    # Convert to dict for consistency
                    return {
                        'role': msg.role,
                        'content': msg.content,
                        'id': msg.id
                    }
                    
        except Exception as e:
            logger.error(f"Failed to retrieve message from disk: {str(e)}")
            
        return None
    
    def run_agent(self, update_callback: Callable[[str], None]) -> None:
        """
        Run the agent with the given instructions
        
        Args:
            update_callback: Callback function to update the UI with messages
        """
        if self.error:
            update_callback(f"Error: {self.error}")
            logger.error(f"Agent run failed due to initialization error: {self.error}")
            return

        self.running = True
        self.error = None
        
        # Generate a unique ID for the initial message
        initial_message_id = f"user_{self.session_id}_0"
        
        # Start the history with the initial instruction
        self.run_history = [{
            "role": "user", 
            "content": self.instructions,
            "id": initial_message_id
        }]
        
        # Save the initial history
        self._save_history_to_disk()
        
        logger.info("Starting agent run")
        
        max_retries = 3
        retry_count = 0
        
        while self.running:
            try:
                # Get the next action from the AI
                message = self.anthropic_client.get_next_action(self.run_history)
                
                # Add a unique ID to the message for retrieval if needed
                message_index = len(self.run_history)
                if isinstance(message, BetaMessage) and not hasattr(message, 'id'):
                    message.id = f"assistant_{self.session_id}_{message_index}"
                
                # Add to in-memory history
                self.run_history.append(message)
                
                # Periodically save history to disk (every 5 messages)
                if message_index % 5 == 0:
                    self._save_history_to_disk()
                
                retry_count = 0  # Reset retry counter on successful call
                logger.debug(f"Received message from Anthropic: {message}")
                
                # Display assistant's message in the chat
                self.display_assistant_message(message, update_callback)
                
                # Extract action from message
                action = self.extract_action(message)
                logger.info(f"Extracted action: {action}")
                
                # Set last_action to enable more intelligent region selection
                if hasattr(self, 'last_action'):
                    action['last_action'] = self.last_action
                    
                # Remember this action for next time
                self.last_action = action.copy() if isinstance(action, dict) else None
                
                if action['type'] == 'error':
                    self.error = action['message']
                    update_callback(f"Error: {self.error}")
                    logger.error(f"Action extraction error: {self.error}")
                    self.running = False
                    break
                elif action['type'] == 'finish':
                    is_successful = action.get('success', True)
                    if is_successful:
                        update_callback("Task completed successfully.")
                        logger.info("Task completed successfully")
                    else:
                        error_msg = action.get('error', 'Unknown error')
                        update_callback(f"Task completed with error: {error_msg}")
                        logger.info(f"Task completed with error: {error_msg}")
                    
                    self.running = False
                    break
                
                try:
                    # Configure screenshot options based on settings
                    action_type = action.get('type', '')
                    
                    # Apply appropriate screenshot optimizations based on action type and setting
                    if self.config:
                        optimization = self.config.get('computer', 'screenshot_optimization', 'balanced')
                        
                        if optimization == 'aggressive':
                            # Skip screenshots for mouse_move and similar non-changing actions
                            if action_type in ['mouse_move', 'cursor_position']:
                                action['skip_before_screenshot'] = True
                                action['skip_after_screenshot'] = True
                            # Use grayscale for most operations
                            action['grayscale'] = True
                        elif optimization == 'balanced':
                            # Skip before screenshots for most actions to save bandwidth
                            if action_type in ['mouse_move', 'cursor_position', 'left_click', 'right_click']:
                                action['skip_before_screenshot'] = True
                        # 'minimal' optimization keeps all screenshots for maximum visual feedback
                    
                    # Perform the action and get the screenshot
                    screenshot = self.computer_control.perform_action(action)
                    
                    if screenshot:  # Only add screenshot if one was returned
                        # Use minimal or no text description to save on tokens
                        description = "" # Empty text saves maximum tokens
                        
                        # Create unique ID for this message
                        message_id = f"user_{self.session_id}_{len(self.run_history)}"
                        
                        # Create a metadata object with useful context
                        metadata = {}
                        
                        # Add action type for context
                        if action_type:
                            metadata['action_type'] = action_type
                            
                        # Add screen coordinates for mouse actions if available
                        if action_type in ['mouse_move', 'left_click_drag'] and 'x' in action and 'y' in action:
                            metadata['coordinates'] = [action['x'], action['y']]
                            
                        # Add region info if specified
                        if region:
                            metadata['region'] = region
                            
                        # Add image processing info
                        metadata['grayscale'] = bool(use_grayscale) if 'use_grayscale' in locals() else False
                        metadata['bw_mode'] = bool(use_bw_mode) if 'use_bw_mode' in locals() else False
                        
                        # Create message with screenshot
                        screenshot_message = {
                            "role": "user",
                            "id": message_id,
                            "metadata": metadata,
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": self.last_tool_use_id,
                                    "content": [
                                        # Only include text if there's an actual description
                                        *([{"type": "text", "text": description}] if description else []),
                                        {"type": "image", "source": {"type": "base64", "media_type": "image/webp", "data": screenshot}}
                                    ]
                                }
                            ]
                        }
                        
                        # Add to run history
                        self.run_history.append(screenshot_message)
                        logger.debug("Screenshot added to run history")
                    
                except Exception as action_error:
                    error_msg = f"Action failed: {str(action_error)}"
                    update_callback(f"Error: {error_msg}")
                    logger.error(error_msg)
                    # Don't stop running, let the AI handle the error
                    error_msg_id = f"user_{self.session_id}_{len(self.run_history)}"
                    self.run_history.append({
                        "role": "user",
                        "id": error_msg_id,
                        "content": [{"type": "text", "text": error_msg}]
                    })
                
            except AnthropicError as e:
                # Handle specific Anthropic errors
                if e.status_code == 429 and retry_count < max_retries:
                    # Rate limit retry with backoff
                    retry_count += 1
                    wait_time = retry_count * 2  # Exponential backoff
                    update_callback(f"Rate limit reached. Retrying in {wait_time} seconds...")
                    logger.warning(f"Rate limit reached. Retry {retry_count}/{max_retries} in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                
                self.error = str(e)
                update_callback(f"Anthropic API Error: {self.error}")
                logger.error(f"Anthropic API error during agent run: {self.error}")
                self.running = False
                break
                
            except Exception as e:
                self.error = str(e)
                update_callback(f"Error: {self.error}")
                logger.exception(f"Unexpected error during agent run: {self.error}")
                self.running = False
                break
        
    def stop_run(self) -> None:
        """Stop the current agent run and clean up resources"""
        self.running = False
        if hasattr(self, 'computer_control'):
            self.computer_control.cleanup()
        logger.info("Agent run stopped")
        
        # Add a message to the run history to indicate stopping
        stop_message_id = f"user_{self.session_id}_{len(self.run_history)}"
        self.run_history.append({
            "role": "user",
            "id": stop_message_id,
            "content": [{"type": "text", "text": "Agent run stopped by user."}]
        })
        
        # Final save of the full history to disk
        self._save_history_to_disk()
        
    def get_message_history(self, start_index: int = 0, count: int = None) -> List[Dict[str, Any]]:
        """
        Retrieve a slice of the message history
        
        Args:
            start_index: The index to start from
            count: The number of messages to retrieve, or None for all messages
            
        Returns:
            A list of messages
        """
        end_index = None if count is None else start_index + count
        return self.run_history[start_index:end_index]
    
    def get_session_info(self) -> Dict[str, Any]:
        """
        Get information about the current session
        
        Returns:
            Dict with session info
        """
        return {
            'session_id': self.session_id,
            'start_time': self.session_id[:15].replace('_', ' '),
            'message_count': len(self.run_history),
            'history_file': str(self.history_file),
            'history_index_file': str(self.history_index_file)
        }
        
    def extract_action(self, message: BetaMessage) -> Dict[str, Any]:
        """
        Extract the action from a message
        
        Args:
            message: The message to extract the action from
            
        Returns:
            Dict containing the action parameters
        """
        logger.debug(f"Extracting action from message: {message}")
        try:
            if not isinstance(message, BetaMessage):
                logger.error(f"Unexpected message type: {type(message)}")
                return {'type': 'error', 'message': 'Unexpected message type'}
            
            for item in message.content:
                if isinstance(item, BetaToolUseBlock):
                    tool_use = item
                    logger.debug(f"Found tool use: {tool_use}")
                    self.last_tool_use_id = tool_use.id
                    
                    if tool_use.name == 'finish_run':
                        success = tool_use.input.get('success', True)
                        error = tool_use.input.get('error', '')
                        return {
                            'type': 'finish',
                            'success': success,
                            'error': error
                        }
                    
                    if tool_use.name != 'computer':
                        logger.error(f"Unexpected tool: {tool_use.name}")
                        return {'type': 'error', 'message': f"Unexpected tool: {tool_use.name}"}
                    
                    input_data = tool_use.input
                    
                    # Handle different formats for action_type
                    # First check for action_type directly in input_data (mock API format)
                    action_type = input_data.get('action_type')
                    
                    # If not found, try the standard 'action' field
                    if action_type is None:
                        action_type = input_data.get('action')
                    
                    # If still None, use a fallback
                    if action_type is None:
                        logger.error(f"Action type not found in input data: {input_data}")
                        return {'type': 'error', 'message': 'Action type not found in input data'}
                    
                    # Start building the action dict
                    action = {'type': action_type}
                    
                    # Process all common screenshot optimization parameters
                    if 'grayscale' in input_data:
                        action['grayscale'] = bool(input_data['grayscale'])
                    
                    if 'bw_mode' in input_data:
                        action['bw_mode'] = bool(input_data['bw_mode'])
                    
                    if 'skip_before_screenshot' in input_data:
                        action['skip_before_screenshot'] = bool(input_data['skip_before_screenshot'])
                        
                    if 'skip_after_screenshot' in input_data:
                        action['skip_after_screenshot'] = bool(input_data['skip_after_screenshot'])
                    
                    # Process region-related parameters
                    if 'region' in input_data and isinstance(input_data['region'], list) and len(input_data['region']) == 4:
                        action['region'] = tuple(input_data['region'])
                        
                    if 'element_type' in input_data:
                        action['element_type'] = input_data['element_type']
                    
                    # Handle action-specific parameters
                    if action_type in ['mouse_move', 'left_click_drag']:
                        # Check both coordinate format and direct x,y format
                        if 'coordinate' in input_data and isinstance(input_data['coordinate'], list) and len(input_data['coordinate']) == 2:
                            action['x'] = input_data['coordinate'][0]
                            action['y'] = input_data['coordinate'][1]
                        elif 'x' in input_data and 'y' in input_data:
                            action['x'] = input_data['x']
                            action['y'] = input_data['y']
                        else:
                            logger.error(f"Invalid coordinate for mouse action: {input_data}")
                            return {'type': 'error', 'message': 'Invalid coordinate for mouse action'}
                        return action
                    elif action_type in ['left_click', 'right_click', 'middle_click', 'double_click', 'mouse_click']:
                        # Include x,y coordinates if available
                        if 'x' in input_data and 'y' in input_data:
                            action['x'] = input_data['x']
                            action['y'] = input_data['y']
                        elif 'coordinate' in input_data and isinstance(input_data['coordinate'], list) and len(input_data['coordinate']) == 2:
                            action['x'] = input_data['coordinate'][0]
                            action['y'] = input_data['coordinate'][1]
                        return action
                    elif action_type in ['screenshot', 'cursor_position']:
                        return action
                    elif action_type in ['type', 'key', 'keyboard_type']:
                        if 'text' not in input_data:
                            logger.error(f"Missing text for keyboard action: {input_data}")
                            return {'type': 'error', 'message': 'Missing text for keyboard action'}
                        action['text'] = input_data['text']
                        return action
                    else:
                        logger.error(f"Unsupported action: {action_type}")
                        return {'type': 'error', 'message': f"Unsupported action: {action_type}"}
            
            logger.error("No tool use found in message")
            return {'type': 'error', 'message': 'No tool use found in message'}
        except Exception as e:
            logger.error(f"Error extracting action: {e}")
            return {'type': 'error', 'message': f"Error extracting action: {e}"}

    def display_assistant_message(self, message: BetaMessage, update_callback: Callable[[str], None]) -> None:
        """
        Display the assistant's message in the UI
        
        Args:
            message: The message to display
            update_callback: Callback function to update the UI
        """
        try:
            if isinstance(message, BetaMessage):
                for item in message.content:
                    if isinstance(item, BetaTextBlock):
                        # Clean and format the text
                        text = item.text.strip()
                        if text:  # Only send non-empty messages
                            update_callback(f"Assistant: {text}")
                    elif isinstance(item, BetaToolUseBlock):
                        # Format tool use in a more readable way
                        tool_name = item.name
                        tool_input = item.input
                        
                        # Convert tool use to a more readable format
                        if tool_name == 'computer':
                            # Check for both action formats
                            action_type = tool_input.get('action_type')
                            if action_type is None:
                                action_type = tool_input.get('action')
                            
                            # Build a standardized action dict for display
                            action = {'type': action_type}
                            
                            # Handle coordinates
                            if 'x' in tool_input and 'y' in tool_input:
                                action['x'] = tool_input.get('x')
                                action['y'] = tool_input.get('y')
                            elif 'coordinate' in tool_input and isinstance(tool_input['coordinate'], list) and len(tool_input['coordinate']) == 2:
                                action['x'] = tool_input['coordinate'][0]
                                action['y'] = tool_input['coordinate'][1]
                                
                            # Handle text for keyboard actions
                            if 'text' in tool_input:
                                action['text'] = tool_input.get('text')
                                
                            update_callback(f"Action: {json.dumps(action)}")
                        elif tool_name == 'finish_run':
                            success = tool_input.get('success', True)
                            if success:
                                update_callback("Assistant: Task completed successfully!")
                            else:
                                error = tool_input.get('error', 'Unknown error')
                                update_callback(f"Assistant: Task could not be completed: {error}")
                        else:
                            update_callback(f"Assistant action: {tool_name} - {json.dumps(tool_input)}")
        except Exception as e:
            logger.error(f"Error displaying assistant message: {e}")
            update_callback(f"Error displaying message: {str(e)}")

    def cleanup(self) -> None:
        """Clean up resources"""
        if hasattr(self, 'computer_control'):
            self.computer_control.cleanup()
            
        # Final save of history before cleanup
        if hasattr(self, 'run_history') and self.run_history:
            self._save_history_to_disk()
            logger.info(f"Final history saved to {self.history_file}")
