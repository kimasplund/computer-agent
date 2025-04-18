# 👨🏽‍💻 Grunty

Self-hosted desktop app to have AI control your computer, powered by the new Claude [computer use](https://www.anthropic.com/news/3-5-models-and-computer-use) capability. Allow Claude to take over your laptop and do your tasks for you (or at least attempt to, lol). Written in Python, using PyQt.

## Demo
Here, I asked it to use [vim](https://vim.rtorr.com/) to create a game in Python, run it, and play it.

https://github.com/user-attachments/assets/fa9b195e-fae6-4dbc-adb9-dc42519624b1

Video was sped up 8x btw. [Computer use](https://www.anthropic.com/news/3-5-models-and-computer-use) is pretty slow as of today.

## ⚠️ Important Disclaimers

1. **This is experimental software** - It gives an AI control of your mouse and keyboard. Things can and will go wrong.

2. **Tread Lightly** - If it wipes your computer, sends weird emails, or orders 100 pizzas... that's on you. 

Anthropic can see your screen through screenshots during actions. Hide sensitive information or private stuff.

## 🎯 Features
- Literally ask AI to do ANYTHING on your computer that you do with a mouse and keyboard. Browse the web, write code, blah blah.
- **NEW**: Improved error handling and retry logic for API calls
- **NEW**: Better token management to optimize costs
- **NEW**: Type hinting for Python 3.13 compatibility
- **NEW**: Centralized configuration management

# 💻 Platforms
- Anything you can run Python on: MacOS, Windows, Linux, etc.

## 🛠️ Setup

Get an Anthropic API key [here]([https://console.anthropic.com/keys](https://console.anthropic.com/dashboard)).

```bash
# Python 3.10+ recommended
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Copy the example .env file and configure your settings
cp .env.example .env
# Edit .env with your API key
nano .env  # or use any text editor

# Run
python run.py
```

## 🔑 Productivity Keybindings
- `Ctrl + Enter`: Execute the current instruction
- `Ctrl + C`: Stop the current agent action
- `Ctrl + W`: Minimize to system tray
- `Ctrl + Q`: Quit application

## 💡 Tips
- Claude really loves Firefox. You might want to install it for better UI detection and accurate mouse clicks.
- Be specific and explicit, help it out a bit
- Always monitor the agent's actions

## Recent Improvements

### Enhanced Anthropic Client
- Implemented automatic retries for rate limiting and timeouts
- Added proper token counting with fallback mechanism
- Improved error handling with custom exceptions
- Better configuration management through centralized config
- Type hinting for better IDE support and code quality

### Improved Store Module
- Better state management for running tasks
- Enhanced error handling and recovery
- Proper typing for all methods and properties
- More detailed reporting during task execution

## 🐛 Known Issues

- Sometimes, it doesn't take a screenshot to validate that the input is selected, and types stuff in the wrong place.. Press CMD+C to end the action when this happens, and quit and restart the agent. I'm working on a fix.

## 🤝 Contributing

Issues and PRs are most welcome! Made this is in a day so don't really have a roadmap in mind. Hmu on Twitter @ishanxnagpal if you're got interesting ideas you wanna share. 

## 📄 License

[Apache License 2.0](LICENSE)

## Wayland Multi-Screen Support

This application now includes improved support for Wayland environments with multiple displays. The following features are available:

### Wayland-Specific Features

- Automatic detection of Wayland environment
- Proper window positioning across multiple screens
- Handling of screen addition/removal events
- High DPI screen support with automatic scaling
- Screen-specific configuration options

### Troubleshooting Wayland Issues

If you encounter issues with the application on Wayland, try the following:

1. **Debug Mode**: Press `Alt+Right-click` anywhere on the application window to open the debug dialog, which displays detailed information about screens, environment variables and settings.

2. **Command Line Options**:
   - `--no-wayland`: Disable Wayland-specific features
   - `--force-x11`: Force using X11 platform plugin instead of Wayland
   - `--debug-screens`: Enable detailed screen debugging logs
   - `--scale-factor [value]`: Set a custom scale factor (e.g., 1.5)

3. **Environment Variables**:
   - `WAYLAND_ENABLED=false`: Disable Wayland support
   - `QT_SCALE_FACTOR=1.5`: Set custom scaling factor
   - `QT_WAYLAND_DISABLE_WINDOWDECORATION=1`: Remove window decorations
   - `QT_QPA_PLATFORM=xcb`: Force X11 backend

### Example Usage

```bash
# Run with Wayland debugging enabled
python run.py --debug-screens

# Force X11 mode if Wayland causes issues
python run.py --force-x11

# Set custom scale factor for high DPI displays
python run.py --scale-factor 1.5
```

If you continue to experience issues with Wayland, try creating a `.env` file with the following content:

```
WAYLAND_ENABLED=false
```

## Development and Testing

### Mock API Mode

For development and testing when you don't have Anthropic API credits, you can use the mock API mode:

1. Add the following to your `.env` file:
   ```
   USE_MOCK_API=true
   ```

2. Alternatively, you can enable it in the configuration:
   ```python
   config.set("api", "use_mock_api", True)
   ```

3. You can also set it to automatically fall back to mock mode if the API fails:
   ```
   FALLBACK_TO_MOCK_ON_ERROR=true
   ```

When mock API mode is enabled, the system will generate simulated responses instead of calling the Anthropic API. This is useful for:

- Testing UI and app behavior without API costs
- Developing new features without API access
- Testing the app in environments without internet access
- Continuing to use the app when you run out of API credits
- Handling API outages gracefully

The mock responses are simplified but follow the same format as real API responses, simulating basic behaviors like:
- Taking screenshots
- Clicking on screen positions
- Typing text
- Completing tasks

### Token Counting

If you encounter token counting errors, you can install the `tiktoken` package for a reliable local fallback:

```bash
pip install tiktoken
```

This provides a local tokenizer that works with Claude models without requiring API calls.