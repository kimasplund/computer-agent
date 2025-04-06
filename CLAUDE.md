# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands
- Run application: `python run.py`
- No formal testing infrastructure yet (future improvement planned)

## Code Style Guidelines
- **Imports**: System imports first, third-party second, local modules last; use explicit imports
- **Formatting**: Follow PEP 8 conventions; use proper indentation (4 spaces)
- **Types**: Use type hints for all functions and method signatures; import from typing module
- **Naming**: CamelCase for classes, snake_case for functions/variables, UPPER_SNAKE_CASE for constants
- **Error Handling**: Use custom exceptions from src/exceptions.py; wrap external calls in try/except
- **Logging**: Use the logger module (src/logger.py) instead of print statements
- **Documentation**: Add docstrings to classes and functions with descriptions and parameter details
- **Modules**: Follow modular architecture with clear separation of concerns

## Performance Guidelines
- **Images**: Use WebP format with appropriate quality settings (see COMPUTER_CONFIG)
- **Screenshots**: Use region-specific captures when possible to reduce size
- **UI Updates**: Minimize token usage by keeping text descriptions brief

## Python Package Guidelines
When working with Python packages, use MCP-PyPI for checking package information, following guidelines in .cursor/rules/handling-python-packages.mdc