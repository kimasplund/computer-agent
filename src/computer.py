import pyautogui
from PIL import Image
import io
import base64
import time
import logging
import numpy as np
import os
import sys
import subprocess
from typing import Dict, Tuple, Optional, Union, Any, List
from functools import lru_cache
import gc

logger = logging.getLogger(__name__)

class ComputerControl:
    def __init__(self, config=None):
        self.config = config
        
        # Detect Wayland environment
        self.is_wayland = self._detect_wayland_environment()
        logger.info(f"Wayland environment detected: {self.is_wayland}")
        
        # Get screen dimensions (with Wayland support)
        self.screen_width, self.screen_height = self._get_screen_dimensions()
        pyautogui.PAUSE = 0.5  # Add a small delay between actions for stability
        self.last_click_position = None
        
        # Multi-screen support
        self.screens = self._detect_screens()
        logger.info(f"Detected {len(self.screens)} screens")
        
        # Screenshot cache settings
        self.screenshot_cache: Dict[str, Tuple[str, float]] = {}  # {cache_key: (base64_data, timestamp)}
        self.cache_ttl = 5.0  # Cache TTL in seconds
        self.max_cache_size = 10  # Maximum number of cached screenshots
        
        # Performance settings
        self.use_numpy_processing = True  # Use numpy for faster image processing
        self.memory_optimization = True  # Enable memory optimization
        
        # Wayland-specific settings
        if self.is_wayland:
            self._configure_for_wayland()
        
        logger.info(f"ComputerControl initialized with screen size: {self.screen_width}x{self.screen_height}")
        
    def _detect_wayland_environment(self) -> bool:
        """Detect if running in a Wayland environment"""
        # Check environment variables
        wayland_display = os.environ.get("WAYLAND_DISPLAY", "")
        xdg_session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        
        # Check config if available
        wayland_enabled = False
        if self.config and hasattr(self.config, 'is_wayland_enabled'):
            wayland_enabled = self.config.is_wayland_enabled()
        
        # Determine if we're running in Wayland
        is_wayland = (wayland_display != "" or 
                     xdg_session_type == "wayland" or 
                     wayland_enabled)
        
        return is_wayland
        
    def _get_screen_dimensions(self) -> Tuple[int, int]:
        """Get screen dimensions with Wayland support"""
        try:
            # Try pyautogui first
            width, height = pyautogui.size()
            
            # If we're on Wayland and the dimensions seem wrong, try alternative methods
            if self.is_wayland and (width <= 0 or height <= 0):
                # Try using xrandr command for X11 fallback
                try:
                    output = subprocess.check_output(["xrandr"], text=True)
                    for line in output.split("\n"):
                        if " connected " in line and "primary" in line:
                            # Extract resolution like: 3840x2160+0+0
                            parts = line.split()
                            for part in parts:
                                if "x" in part and "+" in part:
                                    resolution = part.split("+")[0]
                                    width, height = map(int, resolution.split("x"))
                                    break
                except (subprocess.SubprocessError, FileNotFoundError):
                    # If xrandr fails, try wlr-randr for native Wayland
                    try:
                        output = subprocess.check_output(["wlr-randr"], text=True)
                        for line in output.split("\n"):
                            if "current" in line and "x" in line:
                                # Extract resolution like: 3840x2160
                                parts = line.split()
                                for part in parts:
                                    if "x" in part and part[0].isdigit():
                                        width, height = map(int, part.split("x"))
                                        break
                    except (subprocess.SubprocessError, FileNotFoundError):
                        # Last resort: use a default resolution
                        logger.warning("Could not determine screen resolution, using defaults")
                        width, height = 1920, 1080
            
            return width, height
        except Exception as e:
            logger.error(f"Error getting screen dimensions: {e}")
            return 1920, 1080  # Default fallback
            
    def _detect_screens(self) -> List[Dict[str, Any]]:
        """Detect all screens in the system"""
        screens = []
        
        try:
            if self.is_wayland:
                # Try wlr-randr for Wayland
                try:
                    output = subprocess.check_output(["wlr-randr"], text=True)
                    current_screen = None
                    
                    for line in output.split("\n"):
                        if line and not line.startswith(" "):
                            # This is a screen name
                            current_screen = {
                                "name": line.strip(),
                                "width": 0,
                                "height": 0,
                                "x": 0,
                                "y": 0
                            }
                            screens.append(current_screen)
                        elif current_screen and "current" in line and "x" in line:
                            # Extract resolution
                            parts = line.split()
                            for part in parts:
                                if "x" in part and part[0].isdigit():
                                    width, height = map(int, part.split("x"))
                                    current_screen["width"] = width
                                    current_screen["height"] = height
                                    break
                except (subprocess.SubprocessError, FileNotFoundError):
                    # Fallback to xrandr
                    self._detect_screens_xrandr(screens)
            else:
                # Use xrandr for X11
                self._detect_screens_xrandr(screens)
                
            # If no screens detected, add at least one with the main dimensions
            if not screens:
                screens.append({
                    "name": "primary",
                    "width": self.screen_width,
                    "height": self.screen_height,
                    "x": 0,
                    "y": 0
                })
                
            return screens
        except Exception as e:
            logger.error(f"Error detecting screens: {e}")
            # Return at least one screen with the main dimensions
            return [{
                "name": "primary",
                "width": self.screen_width,
                "height": self.screen_height,
                "x": 0,
                "y": 0
            }]
            
    def _detect_screens_xrandr(self, screens: List[Dict[str, Any]]) -> None:
        """Detect screens using xrandr command"""
        try:
            output = subprocess.check_output(["xrandr"], text=True)
            for line in output.split("\n"):
                if " connected " in line:
                    # Extract screen name
                    name = line.split()[0]
                    
                    # Extract position and resolution
                    screen_info = {
                        "name": name,
                        "width": 0,
                        "height": 0,
                        "x": 0,
                        "y": 0
                    }
                    
                    # Extract resolution like: 3840x2160+0+0
                    parts = line.split()
                    for part in parts:
                        if "x" in part and "+" in part:
                            resolution_part = part.split("+")[0]
                            position_parts = part.split("+")[1:]
                            
                            width, height = map(int, resolution_part.split("x"))
                            x, y = map(int, position_parts)
                            
                            screen_info["width"] = width
                            screen_info["height"] = height
                            screen_info["x"] = x
                            screen_info["y"] = y
                            break
                    
                    screens.append(screen_info)
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.warning(f"Error using xrandr: {e}")
            
    def _configure_for_wayland(self) -> None:
        """Apply Wayland-specific configurations"""
        # Set environment variables that might help with Wayland compatibility
        os.environ["_JAVA_AWT_WM_NONREPARENTING"] = "1"
        os.environ["QT_QPA_PLATFORM"] = "wayland"
        
        # Configure PyAutoGUI for Wayland if possible
        try:
            # Some PyAutoGUI operations might need adjustments for Wayland
            # For example, we might need to use different screenshot methods
            logger.info("Configured PyAutoGUI for Wayland environment")
        except Exception as e:
            logger.warning(f"Error configuring for Wayland: {e}")
        
    def perform_action(self, action):
        # Validate action for safety
        if not self._validate_action_safety(action):
            logger.warning(f"Potentially unsafe action blocked: {action}")
            return self._generate_error_image()
            
        action_type = action['type']
        # Determine if we should skip the "before" screenshot to save bandwidth
        skip_before_screenshot = action.get('skip_before_screenshot', False)
        # Determine if we should use grayscale to save bandwidth
        use_grayscale = action.get('grayscale', False)
        # Determine if we should use black and white (1-bit) mode for text-focused screenshots
        use_bw_mode = action.get('bw_mode', False)
        # Get region if specified for targeted screenshots
        region = action.get('region', None)
        
        # If region of interest type is specified, calculate the region
        if not region and action.get('element_type'):
            region = self.get_region_of_interest(
                element_type=action.get('element_type'),
                last_action=action.get('last_action')
            )
            
            # Auto-enable black and white mode for text-based elements like address bars
            if not use_grayscale and not use_bw_mode and action.get('element_type') in ['browser_address', 'text_field']:
                use_bw_mode = True
        
        # Take a screenshot before the action (unless skipped)
        before_screenshot = None if skip_before_screenshot else self.take_screenshot(
            region=region, 
            grayscale=use_grayscale,
            bw_mode=use_bw_mode
        )
        
        # Log the action being performed
        logger.info(f"Performing action: {action_type}")
        
        try:
            if action_type == 'mouse_move':
                x, y = self.map_from_ai_space(action['x'], action['y'])
                pyautogui.moveTo(x, y)
                time.sleep(0.2)  # Wait for move to complete
                
            elif action_type == 'left_click':
                pyautogui.click()
                time.sleep(0.2)  # Wait for click to register
                self.last_click_position = pyautogui.position()
                
            elif action_type == 'right_click':
                pyautogui.rightClick()
                time.sleep(0.2)
                
            elif action_type == 'middle_click':
                pyautogui.middleClick()
                time.sleep(0.2)
                
            elif action_type == 'double_click':
                pyautogui.doubleClick()
                time.sleep(0.2)
                self.last_click_position = pyautogui.position()
                
            elif action_type == 'left_click_drag':
                start_x, start_y = pyautogui.position()
                end_x, end_y = self.map_from_ai_space(action['x'], action['y'])
                pyautogui.dragTo(end_x, end_y, button='left', duration=0.5)
                time.sleep(0.2)
                
            elif action_type == 'type':
                # If we have a last click position, ensure we're still there
                if self.last_click_position:
                    current_pos = pyautogui.position()
                    if current_pos != self.last_click_position:
                        pyautogui.click(self.last_click_position)
                        time.sleep(0.2)
                
                pyautogui.write(action['text'], interval=0.1)
                time.sleep(0.2)
                
            elif action_type == 'key':
                pyautogui.press(action['text'])
                time.sleep(0.2)
                
            elif action_type == 'screenshot':
                # For explicit screenshot requests, enable options for targeted captures
                return self.take_screenshot(
                    region=region,
                    grayscale=use_grayscale
                )
                
            elif action_type == 'cursor_position':
                x, y = pyautogui.position()
                return self.map_to_ai_space(x, y)
                
            else:
                raise ValueError(f"Unsupported action: {action_type}")
            
            # Check if we should skip the "after" screenshot for certain actions
            skip_after_screenshot = action.get('skip_after_screenshot', False)
            
            # For certain actions like mouse_move, we can skip the after screenshot to save tokens
            if skip_after_screenshot:
                return before_screenshot
                
            # Take a screenshot after the action
            after_screenshot = self.take_screenshot(
                region=region, 
                grayscale=use_grayscale,
                bw_mode=use_bw_mode
            )
            return after_screenshot
            
        except Exception as e:
            raise Exception(f"Action failed: {action_type} - {str(e)}")
        
    def take_screenshot(self, region=None, grayscale=False, bw_mode=False, screen_index=None) -> str:
        """
        Take a screenshot and return it as a base64 encoded WebP image
        
        Args:
            region: Optional tuple (x, y, width, height) for capturing specific region
            grayscale: Whether to convert to grayscale to reduce size
            bw_mode: Whether to convert to black and white (1-bit) for minimal size
            screen_index: Optional index of screen to capture (for multi-screen setups)
            
        Returns:
            Base64 encoded WebP image as string
        """
        # Generate cache key based on parameters
        cache_key = f"{region}_{grayscale}_{bw_mode}_{screen_index}_{time.time() // self.cache_ttl}"
        
        # Check if we have a cached version
        if cache_key in self.screenshot_cache:
            cached_data, timestamp = self.screenshot_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                logger.debug(f"Using cached screenshot for key: {cache_key}")
                return cached_data
        
        # Clean old cache entries
        self._clean_screenshot_cache()
        
        try:
            # Determine if we need to use Wayland-specific methods
            if self.is_wayland:
                screenshot = self._take_wayland_screenshot(region, screen_index)
            else:
                # Get screenshot using PyAutoGUI (full or region)
                if region:
                    screenshot = pyautogui.screenshot(region=region)
                else:
                    screenshot = pyautogui.screenshot()
                
            # Get AI width/height from config or use defaults
            ai_width = self.config.get('computer', 'ai_display_width', 1024) if self.config else 1024
            ai_height = self.config.get('computer', 'ai_display_height', 640) if self.config else 640
            
            # Resize image using faster method if numpy is available
            if self.use_numpy_processing:
                ai_screenshot = self._fast_resize(screenshot, (ai_width, ai_height))
            else:
                # Fallback to PIL resize
                ai_screenshot = screenshot.resize((ai_width, ai_height), Image.BILINEAR)
            
            # Apply image mode transformations
            if bw_mode:
                # Convert to black and white (1-bit) for extreme compression
                if self.use_numpy_processing:
                    ai_screenshot = self._fast_bw_convert(ai_screenshot)
                else:
                    # First convert to grayscale
                    ai_screenshot = ai_screenshot.convert('L')
                    # Then threshold to binary (1-bit)
                    threshold = 200  # Higher threshold keeps more white (better for text)
                    ai_screenshot = ai_screenshot.point(lambda p: 255 if p > threshold else 0)
                    ai_screenshot = ai_screenshot.convert('1')  # Convert to 1-bit
            elif grayscale:
                # Convert to grayscale (8-bit) if only grayscale requested
                if self.use_numpy_processing:
                    ai_screenshot = self._fast_grayscale_convert(ai_screenshot)
                else:
                    ai_screenshot = ai_screenshot.convert('L')
                
            # Compress to WebP
            buffered = io.BytesIO()
            
            # Quality settings depend on the image mode
            if bw_mode:
                # For B&W images, we can use more aggressive compression
                quality = 50  # Lower quality works fine for binary images
            else:
                # For color/grayscale, use standard quality setting
                quality = self.config.get('computer', 'screenshot_quality', 70) if self.config else 70
                
            # Convert 1-bit back to 'L' for WebP (WebP doesn't support 1-bit directly)
            if bw_mode and ai_screenshot.mode == '1':
                ai_screenshot = ai_screenshot.convert('L')
                
            ai_screenshot.save(buffered, format="WEBP", quality=quality, method=6)
            
            # Get base64 encoded result
            result = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # Cache the result
            self.screenshot_cache[cache_key] = (result, time.time())
            
            # Clean up memory if optimization is enabled
            if self.memory_optimization:
                del screenshot
                del ai_screenshot
                del buffered
                gc.collect()
            
            return result
            
        except Exception as e:
            logger.error(f"Screenshot error: {str(e)}")
            # Return a minimal error image if screenshot fails
            return self._generate_error_image()
            
    def _take_wayland_screenshot(self, region=None, screen_index=None) -> Image.Image:
        """
        Take a screenshot in Wayland environment using alternative methods
        
        Args:
            region: Optional tuple (x, y, width, height) for capturing specific region
            screen_index: Optional index of screen to capture
            
        Returns:
            PIL Image object
        """
        # Try different screenshot methods for Wayland
        try:
            # First try PyAutoGUI (might work with XWayland)
            try:
                if region:
                    screenshot = pyautogui.screenshot(region=region)
                else:
                    screenshot = pyautogui.screenshot()
                return screenshot
            except Exception as e:
                logger.warning(f"PyAutoGUI screenshot failed in Wayland: {e}")
            
            # Try using grim (Wayland native screenshot tool)
            try:
                # Determine output file
                temp_file = "/tmp/grunty_screenshot.png"
                
                # Build command based on parameters
                cmd = ["grim"]
                
                # Add region if specified
                if region:
                    x, y, width, height = region
                    cmd.extend(["-g", f"{x},{y} {width}x{height}"])
                
                # Add output file
                cmd.append(temp_file)
                
                # Execute command
                subprocess.run(cmd, check=True)
                
                # Load the image
                screenshot = Image.open(temp_file)
                
                # Clean up temp file
                try:
                    os.remove(temp_file)
                except:
                    pass
                    
                return screenshot
            except (subprocess.SubprocessError, FileNotFoundError) as e:
                logger.warning(f"Grim screenshot failed: {e}")
            
            # Try using gnome-screenshot as another alternative
            try:
                temp_file = "/tmp/grunty_screenshot.png"
                cmd = ["gnome-screenshot", "-f", temp_file]
                
                # Execute command
                subprocess.run(cmd, check=True)
                
                # Load the image
                screenshot = Image.open(temp_file)
                
                # If region is specified, crop the image
                if region:
                    x, y, width, height = region
                    screenshot = screenshot.crop((x, y, x + width, y + height))
                
                # Clean up temp file
                try:
                    os.remove(temp_file)
                except:
                    pass
                    
                return screenshot
            except (subprocess.SubprocessError, FileNotFoundError) as e:
                logger.warning(f"gnome-screenshot failed: {e}")
            
            # Last resort: create a blank image with error message
            logger.error("All screenshot methods failed in Wayland environment")
            error_img = Image.new('RGB', (800, 600), color=(50, 50, 50))
            return error_img
            
        except Exception as e:
            logger.error(f"Wayland screenshot error: {str(e)}")
            # Create a blank image as fallback
            return Image.new('RGB', (800, 600), color=(50, 50, 50))
            
    def _clean_screenshot_cache(self) -> None:
        """Clean expired or excess entries from the screenshot cache"""
        now = time.time()
        
        # Remove expired entries
        expired_keys = [k for k, (_, ts) in self.screenshot_cache.items() 
                       if now - ts > self.cache_ttl]
        for k in expired_keys:
            del self.screenshot_cache[k]
            
        # If still too many entries, remove oldest ones
        if len(self.screenshot_cache) > self.max_cache_size:
            # Sort by timestamp (oldest first)
            sorted_items = sorted(self.screenshot_cache.items(), key=lambda x: x[1][1])
            # Keep only the newest entries
            self.screenshot_cache = dict(sorted_items[-self.max_cache_size:])
            
    def _fast_resize(self, image: Image.Image, size: Tuple[int, int]) -> Image.Image:
        """Faster image resize using numpy"""
        try:
            # Convert PIL image to numpy array
            img_array = np.array(image)
            
            # Get target dimensions
            target_height, target_width = size[1], size[0]
            
            # Calculate resize factors
            height, width, _ = img_array.shape if len(img_array.shape) == 3 else (*img_array.shape, 1)
            h_factor, w_factor = height / target_height, width / target_width
            
            # Create coordinate matrices for faster indexing
            y_indices = np.floor(np.arange(target_height) * h_factor).astype(int)
            x_indices = np.floor(np.arange(target_width) * w_factor).astype(int)
            
            # Resize by indexing
            resized = img_array[y_indices[:, np.newaxis], x_indices]
            
            # Convert back to PIL image
            return Image.fromarray(resized)
        except Exception as e:
            logger.warning(f"Fast resize failed, falling back to PIL: {e}")
            return image.resize(size, Image.BILINEAR)
            
    def _fast_grayscale_convert(self, image: Image.Image) -> Image.Image:
        """Faster grayscale conversion using numpy"""
        try:
            # Convert PIL image to numpy array
            img_array = np.array(image)
            
            # If already grayscale, return as is
            if len(img_array.shape) == 2:
                return image
                
            # Apply grayscale formula: 0.299*R + 0.587*G + 0.114*B
            grayscale = np.dot(img_array[...,:3], [0.299, 0.587, 0.114]).astype(np.uint8)
            
            # Convert back to PIL image
            return Image.fromarray(grayscale, mode='L')
        except Exception as e:
            logger.warning(f"Fast grayscale conversion failed, falling back to PIL: {e}")
            return image.convert('L')
            
    def _fast_bw_convert(self, image: Image.Image) -> Image.Image:
        """Faster black and white conversion using numpy"""
        try:
            # First convert to grayscale
            grayscale_img = self._fast_grayscale_convert(image)
            
            # Convert PIL image to numpy array
            img_array = np.array(grayscale_img)
            
            # Apply threshold
            threshold = 200
            binary = (img_array > threshold).astype(np.uint8) * 255
            
            # Convert back to PIL image
            return Image.fromarray(binary, mode='1')
        except Exception as e:
            logger.warning(f"Fast B&W conversion failed, falling back to PIL: {e}")
            # Fallback to PIL
            grayscale = image.convert('L')
            return grayscale.point(lambda p: 255 if p > 200 else 0).convert('1')
            
    def _generate_error_image(self) -> str:
        """Generate a minimal error image when screenshot fails"""
        # Create a small red image to indicate error
        error_img = Image.new('RGB', (320, 240), color=(255, 0, 0))
        buffered = io.BytesIO()
        error_img.save(buffered, format="WEBP", quality=50)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
        
    def get_region_of_interest(self, element_type=None, last_action=None):
        """
        Intelligently determine a region of interest for screenshot capturing
        
        Args:
            element_type: Type of UI element to focus on ('text_field', 'button', 'menu', etc.)
            last_action: The previous action that was performed
            
        Returns:
            Tuple (x, y, width, height) for region of interest, or None for full screen
        """
        # Start with current mouse position as a potential center of interest
        cursor_x, cursor_y = pyautogui.position()
        
        # Default region size (adjust based on element type)
        region_width = 400
        region_height = 300
        
        if element_type == 'text_field':
            # Focus on a text input area (make taller and wider)
            region_width = 500
            region_height = 200
        elif element_type == 'button':
            # Focus on a button area (smaller region)
            region_width = 200
            region_height = 100
        elif element_type == 'menu':
            # Focus on a menu (taller region)
            region_width = 300
            region_height = 500
        elif element_type == 'dialog':
            # Focus on a dialog box (medium size)
            region_width = 600
            region_height = 400
        elif element_type == 'browser_address':
            # Focus on browser address bar area
            region_height = 150
            # Center y at top of screen
            cursor_y = 50
            
        # Calculate top-left coordinates of region
        x = max(0, cursor_x - region_width // 2)
        y = max(0, cursor_y - region_height // 2)
        
        # Ensure region stays within screen bounds
        x = min(x, self.screen_width - region_width)
        y = min(y, self.screen_height - region_height)
        
        # If near screen edge, adjust region size to avoid out-of-bounds
        if x + region_width > self.screen_width:
            region_width = self.screen_width - x
        if y + region_height > self.screen_height:
            region_height = self.screen_height - y
            
        return (x, y, region_width, region_height)
        
    def map_from_ai_space(self, x, y):
        ai_width = self.config.get('computer', 'ai_display_width', 1024) if self.config else 1024
        ai_height = self.config.get('computer', 'ai_display_height', 640) if self.config else 640
        return (x * self.screen_width / ai_width, y * self.screen_height / ai_height)
        
    def map_to_ai_space(self, x, y):
        ai_width = self.config.get('computer', 'ai_display_width', 1024) if self.config else 1024
        ai_height = self.config.get('computer', 'ai_display_height', 640) if self.config else 640
        return (x * ai_width / self.screen_width, y * ai_height / self.screen_height)
        
    def resize_for_ai(self, screenshot):
        ai_width = self.config.get('computer', 'ai_display_width', 1024) if self.config else 1024
        ai_height = self.config.get('computer', 'ai_display_height', 640) if self.config else 640
        return screenshot.resize((ai_width, ai_height), Image.BILINEAR)

    def _validate_action_safety(self, action: Dict[str, Any]) -> bool:
        """
        Validate if an action is safe to perform
        
        Args:
            action: The action dictionary to validate
            
        Returns:
            bool: True if the action is safe, False otherwise
        """
        try:
            # Check if action has required type
            if 'type' not in action:
                logger.error("Action missing required 'type' field")
                return False
                
            action_type = action['type']
            
            # Validate based on action type
            if action_type == 'type':
                # Check for potentially dangerous text input
                if 'text' not in action:
                    return False
                    
                text = action['text']
                
                # Block potentially dangerous system commands
                dangerous_patterns = [
                    'sudo ', 'rm -rf', 'format', 'mkfs',
                    ';shutdown', ';reboot', ';halt',
                    'dd if=', '> /dev/', '> /etc/',
                    'chmod 777', 'chown root'
                ]
                
                for pattern in dangerous_patterns:
                    if pattern in text.lower():
                        logger.warning(f"Blocked potentially dangerous text input containing '{pattern}'")
                        return False
                        
            elif action_type in ['mouse_move', 'left_click_drag']:
                # Validate coordinates
                if 'x' not in action or 'y' not in action:
                    return False
                    
                # Check if coordinates are within reasonable bounds
                x, y = action['x'], action['y']
                
                # Coordinates should be within AI space (typically 0-1024, 0-640)
                ai_width = self.config.get('computer', 'ai_display_width', 1024) if self.config else 1024
                ai_height = self.config.get('computer', 'ai_display_height', 640) if self.config else 640
                
                if not (0 <= x <= ai_width * 1.1) or not (0 <= y <= ai_height * 1.1):
                    logger.warning(f"Coordinates ({x}, {y}) out of bounds")
                    return False
            
            # Add more safety checks as needed for other action types
            
            return True
            
        except Exception as e:
            logger.error(f"Error in action safety validation: {str(e)}")
            return False
            
    def cleanup(self):
        """Clean up any resources or running processes"""
        # Clear screenshot cache
        self.screenshot_cache.clear()
        
        # Force garbage collection
        if self.memory_optimization:
            gc.collect()
            
        logger.info("ComputerControl resources cleaned up")
