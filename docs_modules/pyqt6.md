# PyQt6 Documentation

## Overview
PyQt6 is a comprehensive set of Python bindings for Qt v6, implemented as more than 35 extension modules, enabling Python to be used as an alternative application development language to C++ on all supported platforms including iOS and Android.

## Installation
```bash
pip install PyQt6
```

## Key Features
- Complete Python bindings for Qt6
- Support for all major platforms (Windows, macOS, Linux, mobile platforms)
- Cross-platform GUI development
- Access to Qt's rich UI component library
- Signal/slot mechanism for event handling
- Compatible with Python 3.9+

## Basic Usage

### Creating a Simple Window
```python
import sys
from PyQt6.QtWidgets import QApplication, QWidget

app = QApplication(sys.argv)
window = QWidget()
window.setWindowTitle('Simple Window')
window.setGeometry(100, 100, 400, 300)  # Position and size
window.show()

sys.exit(app.exec())
```

### Main Modules
- **QtWidgets**: UI components like buttons, labels, etc.
- **QtCore**: Core non-GUI functionality
- **QtGui**: Window system integration, event handling
- **QtNetwork**: Network programming classes
- **QtMultimedia**: Audio, video, camera functionality
- **QtWebEngineWidgets**: Web browser capabilities

## Current Version
Version: 6.8.1 (as specified in requirements.txt)

## Dependencies
- PyQt6-sip (<14, >=13.8)
- PyQt6-Qt6 (<6.9.0, >=6.8.0)

## Resources
- [Official Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [PyQt6 Homepage](https://www.riverbankcomputing.com/software/pyqt/)
- [PyPI Project Page](https://pypi.org/project/PyQt6/)

## License
PyQt6 is released under the GPL v3 license and under a commercial license that allows for the development of proprietary applications. 