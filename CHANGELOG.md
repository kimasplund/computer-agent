# Changelog

## [Unreleased] - Performance Optimization, Wayland Support, and Enhanced Error Handling

### Added
- Screenshot caching system to avoid redundant captures
- Memory management for large screenshots with automatic cleanup
- Safety mechanisms to prevent dangerous actions
- Enhanced API error handling with more specific exception types
- Improved rate limiting with configurable parameters
- Advanced token counting with multiple fallback mechanisms
- Added tiktoken integration for more accurate token counting
- Comprehensive Wayland support for Ubuntu and other Linux distributions
- Multi-screen detection and handling for complex display setups
- Alternative screenshot methods for Wayland using grim and gnome-screenshot
- Screen geometry detection using both Wayland and X11 methods

### Changed
- Optimized image processing using numpy for better performance
- Improved error recovery with better fallback mechanisms
- Enhanced API retry logic with exponential backoff and jitter
- Added more comprehensive logging throughout the application
- Refactored screen handling to support both X11 and Wayland environments
- Modified screenshot capture to use native Wayland tools when available
- Enhanced multi-screen support with better geometry detection
- Added automatic environment detection for Wayland/X11

### Optimized
- Reduced memory usage for large screenshots
- Improved performance of image transformations
- Added intelligent rate limiting to prevent API throttling
- Enhanced error handling for more robust operation
- Optimized screenshot methods for Wayland with fallback mechanisms
- Improved multi-screen handling for better performance
- Added screen-specific optimizations for complex display setups
- Implemented efficient screen geometry detection

## [Previous] - Screenshot Optimization and Advanced Token Management

### Added
- AI awareness and context preservation:
  - Intelligent truncation summaries of omitted content
  - Rich metadata tracking for screenshot context
  - Token usage tracking and optimization
  - Contextual hints for action types and regions
- Complete local conversation history system:
  - Persistent storage of full conversation history
  - Unique message IDs for tracking and retrieval
  - Session-based organization of history files
  - Retrieval methods for accessing historical messages
  - Automatic preservation of context even when truncated
- Token and response caching system:
  - Caches token counts to reduce API calls
  - Caches identical conversation responses
  - Implements time-based cache expiration (TTL)
  - Adds cache configuration options in API_CONFIG
- Conversation history management:
  - Intelligent truncation of long conversations
  - Retention of initial instructions and recent context
  - Configurable truncation thresholds
  - Minimal empty text descriptors for images
- Black and white (1-bit) mode for extreme size reduction of text-based screenshots
- Region-of-interest capability with predefined element types:
  - `browser_address`: Focus on browser address bar
  - `text_field`: Focus on text input areas
  - `button`: Focus on button areas
  - `menu`: Focus on menu areas
  - `dialog`: Focus on dialog boxes
- Intelligent region selection based on element type
- Context-aware screenshot management with last action tracking
- New configuration options in COMPUTER_CONFIG:
  - `screenshot_use_bw_mode`: Toggle black and white mode
  - `auto_bw_for_text`: Auto-enable B&W for text elements
- Helper method `get_region_of_interest()` for smart region targeting

### Changed
- Reduced default resolution from 1280x800 to 1024x640
- Changed resize algorithm from LANCZOS to BILINEAR for better performance
- Reduced WebP quality from 85% to 70% for standard screenshots
- Added lower quality (50%) for B&W screenshots
- Updated system prompt with screenshot optimization instructions
- Shortened text descriptions in API responses to reduce token usage

### Optimized
- Added intelligent conversation caching based on hash values
- Implemented cache cleaning to prevent memory bloat
- Added auto-skipping of screenshots for non-visual actions
- Added grayscale conversion option (reduces size by ~30%)
- Implemented screenshot optimization strategies (minimal, balanced, aggressive)
- Added options to skip before/after screenshots as needed
- Added automatic B&W conversion for text-focused elements

## [Previous] - WebP Migration

### Changed
- Migrated from PNG to WebP format for screenshots
- Added WebP quality and compression settings
- Updated image handling code to use WebP throughout