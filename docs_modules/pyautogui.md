# PyAutoGUI Documentation

## Overview
PyAutoGUI is a cross-platform GUI automation Python module that enables programmatic control of the mouse and keyboard. It allows you to automate interactions with software applications, making it useful for testing, automation, and scripting.

## Installation
```bash
pip install pyautogui
```

### Dependencies
- **Windows**: No dependencies
- **macOS**: pyobjc-core and pyobjc modules
- **Linux**: python3-xlib module and Pillow dependencies for PNG/JPEG support

## Key Features
- Cross-platform (Windows, macOS, Linux)
- Mouse control (movement, clicking, scrolling)
- Keyboard control (key presses, text typing)
- Screenshot functions
- Image recognition for automation
- Message box display
- Fail-safe mechanism (move mouse to corner to abort)

## Basic Usage

### Mouse Control
```python
import pyautogui

# Get screen size
screenWidth, screenHeight = pyautogui.size()

# Get mouse position
currentX, currentY = pyautogui.position()

# Move mouse to absolute position
pyautogui.moveTo(100, 150)

# Move mouse relative to current position
pyautogui.move(0, 10)  # Move 10 pixels down

# Mouse clicks
pyautogui.click()  # Click at current position
pyautogui.click(200, 220)  # Click at specific position
pyautogui.doubleClick()
pyautogui.rightClick()
pyautogui.middleClick()

# Mouse dragging
pyautogui.dragTo(300, 400, duration=1)  # Drag to position
pyautogui.drag(30, 0, duration=0.5)  # Drag right 30 pixels

# Scrolling
pyautogui.scroll(10)  # Scroll up 10 "clicks"
```

### Keyboard Control
```python
# Type text
pyautogui.write('Hello world!', interval=0.25)  # 0.25s between keystrokes

# Press specific keys
pyautogui.press('esc')
pyautogui.press(['left', 'left', 'left'])  # Press left arrow 3 times

# Key combinations
pyautogui.hotkey('ctrl', 'c')  # Press ctrl+c
pyautogui.keyDown('shift')
pyautogui.press('left')
pyautogui.keyUp('shift')
```

### Screenshots and Image Recognition
```python
# Take screenshot
screenshot = pyautogui.screenshot()
screenshot.save('screen.png')

# Locate image on screen
location = pyautogui.locateOnScreen('button.png')  # Returns (x, y, width, height)

# Get center of found image
buttonX, buttonY = pyautogui.center(location)
pyautogui.click(buttonX, buttonY)  # Click the found image

# Shortcut for locate and click
pyautogui.click('button.png')
```

### Message Boxes
```python
pyautogui.alert('This is an alert box')
response = pyautogui.confirm('Shall I proceed?')  # Returns 'OK' or 'Cancel'
name = pyautogui.prompt('What is your name?')
password = pyautogui.password('Enter password')
```

## Current Version
Version: 0.9.54 (as specified in requirements.txt)

## Safety Features
PyAutoGUI has a failsafe feature - moving the mouse to the upper-left corner (0, 0) will trigger an exception and abort your program. This helps prevent loss of control over your mouse.

```python
# Disable failsafe (not recommended)
pyautogui.FAILSAFE = False
```

## Resources
- [GitHub Repository](https://github.com/asweigart/pyautogui)
- [Official Documentation](https://pyautogui.readthedocs.org)
- [PyPI Project Page](https://pypi.org/project/PyAutoGUI/)

## License
PyAutoGUI is released under the BSD License. 