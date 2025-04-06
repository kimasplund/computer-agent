from PyQt6.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, 
                             QPushButton, QLabel, QProgressBar, QSystemTrayIcon, QMenu, QApplication, QDialog, QLineEdit, QMenuBar, QStatusBar)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QThread, QUrl, QSettings, QRect
from PyQt6.QtGui import QFont, QKeySequence, QShortcut, QAction, QTextCursor, QDesktopServices, QGuiApplication, QCursor
from .store import Store
from .anthropic import AnthropicClient  
from .voice_control import VoiceController
from .prompt_manager import PromptManager
import logging
import qtawesome as qta

logger = logging.getLogger(__name__)

class AgentThread(QThread):
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, store):
        super().__init__()
        self.store = store

    def run(self):
        self.store.run_agent(self.update_signal.emit)
        self.finished_signal.emit()

class SystemPromptDialog(QDialog):
    def __init__(self, parent=None, prompt_manager=None):
        super().__init__(parent)
        self.prompt_manager = prompt_manager
        self.setWindowTitle("Edit System Prompt")
        self.setFixedSize(800, 600)
        
        layout = QVBoxLayout()
        
        # Description
        desc_label = QLabel("Edit the system prompt that defines the agent's behavior. Be careful with changes as they may affect functionality.")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin: 10px 0;")
        layout.addWidget(desc_label)
        
        # Prompt editor
        self.prompt_editor = QTextEdit()
        self.prompt_editor.setPlainText(self.prompt_manager.get_current_prompt())
        self.prompt_editor.setStyleSheet("""
            QTextEdit {
                background-color: #262626;
                border: 1px solid #333333;
                border-radius: 8px;
                color: #ffffff;
                padding: 12px;
                font-family: Inter;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.prompt_editor)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        reset_btn = QPushButton("Reset to Default")
        reset_btn.clicked.connect(self.reset_prompt)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #777777;
            }
        """)
        
        save_btn = QPushButton("Save Changes")
        save_btn.clicked.connect(self.save_changes)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        button_layout.addWidget(reset_btn)
        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def reset_prompt(self):
        if self.prompt_manager.reset_to_default():
            self.prompt_editor.setPlainText(self.prompt_manager.get_current_prompt())
    
    def save_changes(self):
        new_prompt = self.prompt_editor.toPlainText()
        if self.prompt_manager.save_prompt(new_prompt):
            self.accept()
        else:
            # Show error message
            pass

class MainWindow(QMainWindow):
    def __init__(self, store, anthropic_client, config=None):
        super().__init__()
        self.store = store
        self.anthropic_client = anthropic_client
        self.config = config
        self.prompt_manager = PromptManager()
        
        # Initialize theme settings
        self.settings = QSettings('Grunty', 'Preferences')
        self.dark_mode = self.settings.value('dark_mode', True, type=bool)
        
        # Initialize voice control
        self.voice_controller = VoiceController()
        self.voice_controller.voice_input_signal.connect(self.handle_voice_input)
        self.voice_controller.status_signal.connect(self.update_status)
        
        # Status bar for voice feedback
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Voice control ready")
        
        # Initialize screens tracking
        self.screens_list = QGuiApplication.screens()
        self.current_screen = None
        
        # Connect to application screen signals for Wayland
        app = QGuiApplication.instance()
        if hasattr(app, 'screenAdded'):
            app.screenAdded.connect(self.on_screen_added)
        if hasattr(app, 'screenRemoved'):
            app.screenRemoved.connect(self.on_screen_removed)
        
        # Check if API key is missing
        if self.store.error and "ANTHROPIC_API_KEY not found" in self.store.error:
            self.show_api_key_dialog()
        
        self.setWindowTitle("Grunty 👨💻")
        
        # Set size and position - use default values first
        self.setGeometry(100, 100, 400, 600)
        self.setMinimumSize(400, 500)  # Increased minimum size for better usability
        
        # Set rounded corners and border
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setup_ui()
        self.setup_tray()
        self.setup_shortcuts()
        
        # Position window properly on current screen
        self.position_window_on_screen()
        
    def show_api_key_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("API Key Required")
        dialog.setFixedWidth(400)
        
        layout = QVBoxLayout()
        
        # Icon and title
        title_layout = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa5s.key', color='#4CAF50').pixmap(32, 32))
        title_layout.addWidget(icon_label)
        title_label = QLabel("Anthropic API Key Required")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #4CAF50;")
        title_layout.addWidget(title_label)
        layout.addLayout(title_layout)
        
        # Description
        desc_label = QLabel("Please enter your Anthropic API key to continue. You can find this in your Anthropic dashboard.")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin: 10px 0;")
        layout.addWidget(desc_label)
        
        # API Key input
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-ant-...")
        self.api_key_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 2px solid #4CAF50;
                border-radius: 5px;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.api_key_input)
        
        # Save button
        save_btn = QPushButton("Save API Key")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        save_btn.clicked.connect(lambda: self.save_api_key(dialog))
        layout.addWidget(save_btn)
        
        dialog.setLayout(layout)
        dialog.exec()

    def save_api_key(self, dialog):
        api_key = self.api_key_input.text().strip()
        if not api_key:
            return
            
        # Save to .env file
        with open('.env', 'w') as f:
            f.write(f'ANTHROPIC_API_KEY={api_key}')
            
        # Reinitialize the store and anthropic client
        self.store = Store()
        self.anthropic_client = AnthropicClient()
        dialog.accept()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        central_widget.setLayout(main_layout)
        
        # Container widget for rounded corners
        self.container = QWidget()  # Make it an instance variable
        self.container.setObjectName("container")
        container_layout = QVBoxLayout()
        container_layout.setSpacing(0)  # Remove spacing between elements
        self.container.setLayout(container_layout)
        
        # Create title bar
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(10, 5, 10, 5)
        
        # Add Grunty title with robot emoji
        title_label = QLabel("Grunty 🤖")
        title_label.setObjectName("titleLabel")
        title_bar_layout.addWidget(title_label)
        
        # Add File Menu
        file_menu = QMenu("File")
        new_task_action = QAction("New Task", self)
        new_task_action.setShortcut("Ctrl+N")
        edit_prompt_action = QAction("Edit System Prompt", self)
        edit_prompt_action.setShortcut("Ctrl+E")
        edit_prompt_action.triggered.connect(self.show_prompt_dialog)
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.quit_application)
        file_menu.addAction(new_task_action)
        file_menu.addAction(edit_prompt_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)
        
        file_button = QPushButton("File")
        file_button.setObjectName("menuButton")
        file_button.clicked.connect(lambda: file_menu.exec(file_button.mapToGlobal(QPoint(0, file_button.height()))))
        title_bar_layout.addWidget(file_button)
        
        # Add spacer to push remaining items to the right
        title_bar_layout.addStretch()
        
        # Theme toggle button
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("titleBarButton")
        self.theme_button.clicked.connect(self.toggle_theme)
        self.update_theme_button()
        title_bar_layout.addWidget(self.theme_button)
        
        # Minimize and close buttons
        minimize_button = QPushButton("−")
        minimize_button.setObjectName("titleBarButton")
        minimize_button.clicked.connect(self.showMinimized)
        title_bar_layout.addWidget(minimize_button)
        
        close_button = QPushButton("×")
        close_button.setObjectName("titleBarButton")
        close_button.clicked.connect(self.close)
        title_bar_layout.addWidget(close_button)
        
        container_layout.addWidget(title_bar)
        
        # Action log with modern styling
        self.action_log = QTextEdit()
        self.action_log.setReadOnly(True)
        self.action_log.setStyleSheet("""
            QTextEdit {
                background-color: #262626;
                border: none;
                border-radius: 0;
                color: #ffffff;
                padding: 16px;
                font-family: Inter;
                font-size: 13px;
            }
        """)
        container_layout.addWidget(self.action_log, stretch=1)  # Give it flexible space
        
        # Progress bar - Now above input area
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #262626;
                height: 2px;
                margin: 0;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        self.progress_bar.hide()
        container_layout.addWidget(self.progress_bar)

        # Input section container - Fixed height at bottom
        input_section = QWidget()
        input_section.setObjectName("input_section")
        input_section.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                border-top: 1px solid #333333;
            }
        """)
        input_layout = QVBoxLayout()
        input_layout.setContentsMargins(16, 16, 16, 16)
        input_layout.setSpacing(12)
        input_section.setLayout(input_layout)

        # Input area with modern styling
        self.input_area = QTextEdit()
        self.input_area.setPlaceholderText("What can I do for you today?")
        self.input_area.setFixedHeight(100)  # Fixed height for input
        self.input_area.setStyleSheet("""
            QTextEdit {
                background-color: #262626;
                border: 1px solid #333333;
                border-radius: 8px;
                color: #ffffff;
                padding: 12px;
                font-family: Inter;
                font-size: 14px;
                selection-background-color: #4CAF50;
            }
            QTextEdit:focus {
                border: 1px solid #4CAF50;
            }
        """)
        # Connect textChanged signal
        self.input_area.textChanged.connect(self.update_run_button)
        input_layout.addWidget(self.input_area)

        # Control buttons with modern styling
        control_layout = QHBoxLayout()
        
        self.run_button = QPushButton(qta.icon('fa5s.play', color='white'), "Start")
        self.stop_button = QPushButton(qta.icon('fa5s.stop', color='white'), "Stop")
        
        # Connect button signals
        self.run_button.clicked.connect(self.run_agent)
        self.stop_button.clicked.connect(self.stop_agent)
        
        # Initialize button states
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        for button in (self.run_button, self.stop_button):
            button.setFixedHeight(40)
            if button == self.run_button:
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #4CAF50;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        padding: 0 24px;
                        font-family: Inter;
                        font-size: 14px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                    QPushButton:disabled {
                        background-color: #333333;
                        color: #666666;
                    }
                """)
            else:  # Stop button
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #ff4444;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        padding: 0 24px;
                        font-family: Inter;
                        font-size: 14px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #ff3333;
                    }
                    QPushButton:disabled {
                        background-color: #333333;
                        color: #666666;
                    }
                """)
            control_layout.addWidget(button)
        
        # Add voice control button to control layout
        self.voice_button = QPushButton(qta.icon('fa5s.microphone', color='white'), "Voice")
        self.voice_button.setFixedHeight(40)
        self.voice_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 24px;
                font-family: Inter;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:checked {
                background-color: #ff4444;
            }
        """)
        self.voice_button.setCheckable(True)
        self.voice_button.clicked.connect(self.toggle_voice_control)
        control_layout.addWidget(self.voice_button)
        
        input_layout.addLayout(control_layout)

        # Add input section to main container
        container_layout.addWidget(input_section)

        # Add the container to the main layout
        main_layout.addWidget(self.container)
        
        # Apply theme after all widgets are set up
        self.apply_theme()
        
    def update_theme_button(self):
        if self.dark_mode:
            self.theme_button.setIcon(qta.icon('fa5s.sun', color='white'))
            self.theme_button.setToolTip("Switch to Light Mode")
        else:
            self.theme_button.setIcon(qta.icon('fa5s.moon', color='black'))
            self.theme_button.setToolTip("Switch to Dark Mode")

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.settings.setValue('dark_mode', self.dark_mode)
        self.update_theme_button()
        self.apply_theme()

    def apply_theme(self):
        # Apply styles based on theme
        colors = {
            'bg': '#1a1a1a' if self.dark_mode else '#ffffff',
            'text': '#ffffff' if self.dark_mode else '#000000',
            'button_bg': '#333333' if self.dark_mode else '#f0f0f0',
            'button_text': '#ffffff' if self.dark_mode else '#000000',
            'button_hover': '#4CAF50' if self.dark_mode else '#e0e0e0',
            'border': '#333333' if self.dark_mode else '#e0e0e0'
        }

        # Container style
        container_style = f"""
            QWidget#container {{
                background-color: {colors['bg']};
                border-radius: 12px;
                border: 1px solid {colors['border']};
            }}
        """
        self.container.setStyleSheet(container_style)  # Use instance variable

        # Update title label
        self.findChild(QLabel, "titleLabel").setStyleSheet(f"color: {colors['text']}; padding: 5px;")

        # Update action log
        self.action_log.setStyleSheet(f"""
            QTextEdit {{
                background-color: {colors['bg']};
                border: none;
                border-radius: 0;
                color: {colors['text']};
                padding: 16px;
                font-family: Inter;
                font-size: 13px;
            }}
        """)

        # Update input area
        self.input_area.setStyleSheet(f"""
            QTextEdit {{
                background-color: {colors['bg']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
                color: {colors['text']};
                padding: 12px;
                font-family: Inter;
                font-size: 14px;
                selection-background-color: {colors['button_hover']};
            }}
            QTextEdit:focus {{
                border: 1px solid {colors['button_hover']};
            }}
        """)

        # Update progress bar
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background-color: {colors['bg']};
                height: 2px;
                margin: 0;
            }}
            QProgressBar::chunk {{
                background-color: {colors['button_hover']};
            }}
        """)

        # Update input section
        input_section_style = f"""
            QWidget {{
                background-color: {colors['button_bg']};
                border-top: 1px solid {colors['border']};
            }}
        """
        self.findChild(QWidget, "input_section").setStyleSheet(input_section_style)

        # Update window controls style
        window_control_style = f"""
            QPushButton {{
                color: {colors['button_text']};
                background-color: transparent;
                border-radius: 8px;
                padding: 4px 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {colors['button_hover']};
            }}
        """

        # Apply to all window control buttons
        for button in [self.theme_button, 
                      self.findChild(QPushButton, "menuButton"),
                      self.findChild(QPushButton, "titleBarButton")]:
            if button:
                button.setStyleSheet(window_control_style)

        # Update theme button icon
        if self.dark_mode:
            self.theme_button.setIcon(qta.icon('fa5s.sun', color=colors['button_text']))
        else:
            self.theme_button.setIcon(qta.icon('fa5s.moon', color=colors['button_text']))

        # Update tray menu style if needed
        if hasattr(self, 'tray_icon') and self.tray_icon.contextMenu():
            self.tray_icon.contextMenu().setStyleSheet(f"""
                QMenu {{
                    background-color: {colors['bg']};
                    color: {colors['text']};
                    border: 1px solid {colors['border']};
                    border-radius: 6px;
                    padding: 5px;
                }}
                QMenu::item {{
                    padding: 8px 25px 8px 8px;
                    border-radius: 4px;
                }}
                QMenu::item:selected {{
                    background-color: {colors['button_hover']};
                    color: white;
                }}
                QMenu::separator {{
                    height: 1px;
                    background: {colors['border']};
                    margin: 5px 0px;
                }}
            """)
        
    def update_run_button(self):
        self.run_button.setEnabled(bool(self.input_area.toPlainText().strip()))
        
    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        # Make the icon larger and more visible
        icon = qta.icon('fa5s.robot', scale_factor=1.5, color='white')
        self.tray_icon.setIcon(icon)
        
        # Create the tray menu
        tray_menu = QMenu()
        
        # Add a title item (non-clickable)
        title_action = tray_menu.addAction("Grunty 👨🏽‍💻")
        title_action.setEnabled(False)
        tray_menu.addSeparator()
        
        # Add "New Task" option with icon
        new_task = tray_menu.addAction(qta.icon('fa5s.plus', color='white'), "New Task")
        new_task.triggered.connect(self.show)
        
        # Add "Show/Hide" toggle with icon
        toggle_action = tray_menu.addAction(qta.icon('fa5s.eye', color='white'), "Show/Hide")
        toggle_action.triggered.connect(self.toggle_window)
        
        tray_menu.addSeparator()
        
        # Add Quit option with icon
        quit_action = tray_menu.addAction(qta.icon('fa5s.power-off', color='white'), "Quit")
        quit_action.triggered.connect(self.quit_application)
        
        # Style the menu for dark mode
        tray_menu.setStyleSheet("""
            QMenu {
                background-color: #333333;
                color: white;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 25px 8px 8px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #4CAF50;
            }
            QMenu::separator {
                height: 1px;
                background: #444444;
                margin: 5px 0px;
            }
        """)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        # Show a notification when the app starts
        self.tray_icon.showMessage(
            "Grunty is running",
            "Click the robot icon in the menu bar to get started!",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )
        
        # Connect double-click to toggle window
        self.tray_icon.activated.connect(self.tray_icon_activated)

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_window()

    def toggle_window(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def run_agent(self):
        instructions = self.input_area.toPlainText()
        if not instructions:
            self.update_log("Please enter instructions before running the agent.")
            return
        
        self.store.set_instructions(instructions)
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.show()
        self.action_log.clear()
        self.input_area.clear()  # Clear the input area after starting the agent
        
        self.agent_thread = AgentThread(self.store)
        self.agent_thread.update_signal.connect(self.update_log)
        self.agent_thread.finished_signal.connect(self.agent_finished)
        self.agent_thread.start()
        
    def stop_agent(self):
        self.store.stop_run()
        self.stop_button.setEnabled(False)
        
    def agent_finished(self):
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.hide()
        
        # Yellow completion message with sparkle emoji
        completion_message = '''
            <div style="margin: 6px 0;">
                <span style="
                    display: inline-flex;
                    align-items: center;
                    background-color: rgba(45, 45, 45, 0.95);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 100px;
                    padding: 4px 12px;
                    color: #FFD700;
                    font-family: Inter, -apple-system, system-ui, sans-serif;
                    font-size: 13px;
                    line-height: 1.4;
                    white-space: nowrap;
                ">✨ Agent run completed</span>
            </div>
        '''
        self.action_log.append(completion_message)
        
        # Notify voice controller that processing is complete
        if hasattr(self, 'voice_controller'):
            self.voice_controller.finish_processing()
        
        
    def update_log(self, message):
        if message.startswith("Performed action:"):
            action_text = message.replace("Performed action:", "").strip()
            
            # Pill-shaped button style with green text
            button_style = '''
                <div style="margin: 6px 0;">
                    <span style="
                        display: inline-flex;
                        align-items: center;
                        background-color: rgba(45, 45, 45, 0.95);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        border-radius: 100px;
                        padding: 4px 12px;
                        color: #4CAF50;
                        font-family: Inter, -apple-system, system-ui, sans-serif;
                        font-size: 13px;
                        line-height: 1.4;
                        white-space: nowrap;
                    ">{}</span>
                </div>
            '''
            
            try:
                import json
                action_data = json.loads(action_text)
                action_type = action_data.get('type', '').lower()
                
                if action_type == "type":
                    text = action_data.get('text', '')
                    msg = f'⌨️ <span style="margin: 0 4px; color: #4CAF50;">Typed</span> <span style="color: #4CAF50">"{text}"</span>'
                    self.action_log.append(button_style.format(msg))
                    
                elif action_type == "key":
                    key = action_data.get('text', '')
                    msg = f'⌨️ <span style="margin: 0 4px; color: #4CAF50;">Pressed</span> <span style="color: #4CAF50">{key}</span>'
                    self.action_log.append(button_style.format(msg))
                    
                elif action_type == "mouse_move":
                    x = action_data.get('x', 0)
                    y = action_data.get('y', 0)
                    msg = f'🖱️ <span style="margin: 0 4px; color: #4CAF50;">Moved to</span> <span style="color: #4CAF50">({x}, {y})</span>'
                    self.action_log.append(button_style.format(msg))
                    
                elif action_type == "screenshot":
                    msg = '📸 <span style="margin: 0 4px; color: #4CAF50;">Captured Screenshot</span>'
                    self.action_log.append(button_style.format(msg))
                    
                elif "click" in action_type:
                    x = action_data.get('x', 0)
                    y = action_data.get('y', 0)
                    click_map = {
                        "left_click": "Left Click",
                        "right_click": "Right Click",
                        "middle_click": "Middle Click",
                        "double_click": "Double Click"
                    }
                    click_type = click_map.get(action_type, "Click")
                    msg = f'👆 <span style="margin: 0 4px; color: #4CAF50;">{click_type}</span> <span style="color: #4CAF50">({x}, {y})</span>'
                    self.action_log.append(button_style.format(msg))
                    
            except json.JSONDecodeError:
                self.action_log.append(button_style.format(action_text))

        # Clean assistant message style without green background
        elif message.startswith("Assistant:"):
            message_style = '''
                <div style="
                    border-left: 2px solid #666;
                    padding: 8px 16px;
                    margin: 8px 0;
                    font-family: Inter, -apple-system, system-ui, sans-serif;
                    font-size: 13px;
                    line-height: 1.5;
                    color: #e0e0e0;
                ">{}</div>
            '''
            clean_message = message.replace("Assistant:", "").strip()
            self.action_log.append(message_style.format(f'💬 {clean_message}'))

        # Subtle assistant action style
        elif message.startswith("Assistant action:"):
            action_style = '''
                <div style="
                    color: #666;
                    font-style: italic;
                    padding: 4px 0;
                    font-size: 12px;
                    font-family: Inter, -apple-system, system-ui, sans-serif;
                    line-height: 1.4;
                ">🤖 {}</div>
            '''
            clean_message = message.replace("Assistant action:", "").strip()
            self.action_log.append(action_style.format(clean_message))

        # Regular message style
        else:
            regular_style = '''
                <div style="
                    padding: 4px 0;
                    color: #e0e0e0;
                    font-family: Inter, -apple-system, system-ui, sans-serif;
                    font-size: 13px;
                    line-height: 1.4;
                ">{}</div>
            '''
            self.action_log.append(regular_style.format(message))

        # Scroll to bottom
        self.action_log.verticalScrollBar().setValue(
            self.action_log.verticalScrollBar().maximum()
        )
        
    def handle_voice_input(self, text):
        """Handle voice input by setting it in the input area and running the agent"""
        self.input_area.setText(text)
        if text.strip():  # Only run if there's actual text
            self.run_agent()
        
    def update_status(self, message):
        """Update status bar with voice control status"""
        self.status_bar.showMessage(message)
        
    def update_voice_status(self, status):
        """Update the action log with voice control status"""
        status_style = '''
            <div style="margin: 6px 0;">
                <span style="
                    display: inline-flex;
                    align-items: center;
                    background-color: rgba(45, 45, 45, 0.95);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 100px;
                    padding: 4px 12px;
                    color: #4CAF50;
                    font-family: Inter, -apple-system, system-ui, sans-serif;
                    font-size: 13px;
                    line-height: 1.4;
                    white-space: nowrap;
                ">🎤 {}</span>
            </div>
        '''
        self.action_log.append(status_style.format(status))
        
    def toggle_voice_control(self):
        """Toggle voice control on/off"""
        if self.voice_button.isChecked():
            self.voice_controller.toggle_voice_control()
        else:
            self.voice_controller.toggle_voice_control()
            
    def setup_shortcuts(self):
        # Essential shortcuts
        close_window = QShortcut(QKeySequence("Ctrl+W"), self)
        close_window.activated.connect(self.close)
        
        # Add Ctrl+C to stop agent
        stop_agent = QShortcut(QKeySequence("Ctrl+C"), self)
        stop_agent.activated.connect(self.stop_agent)
        
        # Add Ctrl+Enter to send message
        send_message = QShortcut(QKeySequence("Ctrl+Return"), self)
        send_message.activated.connect(self.run_agent)
        
        # Add Alt+V shortcut for voice control
        voice_shortcut = QShortcut(QKeySequence("Alt+V"), self)
        voice_shortcut.activated.connect(lambda: self.voice_button.click())
        
        # Allow tab for indentation
        self.input_area.setTabChangesFocus(False)
        
        # Custom text editing handlers
        self.input_area.keyPressEvent = self.handle_input_keypress

    def handle_input_keypress(self, event):
        # Handle tab key for indentation
        if event.key() == Qt.Key.Key_Tab:
            cursor = self.input_area.textCursor()
            cursor.insertText("    ")  # Insert 4 spaces for tab
            return
            
        # Handle Ctrl+Enter to run agent
        if event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.run_agent()
            return
            
        # For all other keys, use default handling
        QTextEdit.keyPressEvent(self.input_area, event)
        
    def mousePressEvent(self, event):
        self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPosition().toPoint() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPosition().toPoint()
        
        # Check if window moved to a different screen
        self.check_screen_change()

    def check_screen_change(self):
        """Check if the window has moved to a different screen and adjust if needed."""
        window_center = self.geometry().center()
        screens = QGuiApplication.screens()
        
        for screen in screens:
            if screen.geometry().contains(window_center):
                if screen != self.current_screen:
                    # Window moved to a different screen
                    self.current_screen = screen
                    # Apply any screen-specific adjustments if needed
                    self.apply_screen_specific_settings(screen)
                break
    
    def apply_screen_specific_settings(self, screen):
        """Apply any screen-specific settings when moving between screens."""
        # Adjust for screen DPI/scaling if needed
        dpi = screen.logicalDotsPerInch()
        scaling_factor = dpi / 96.0  # 96 is typically the base DPI
        
        # You can adjust font sizes or other UI elements based on scaling
        # For example:
        # if scaling_factor > 1.5:
        #     self.adjustFontSizes(int(12 * scaling_factor))
        
        # Log screen change
        logger.info(f"Window moved to screen: {screen.name()}, DPI: {dpi}, Scaling: {scaling_factor:.2f}")
        
    def closeEvent(self, event):
        """Handle window close event - properly quit the application"""
        self.quit_application()
        event.accept()  # Allow the close
        
    def quit_application(self):
        """Clean up resources and quit the application"""
        # Stop any running agent
        self.store.stop_run()
        
        # Clean up voice control
        if hasattr(self, 'voice_controller'):
            self.voice_controller.cleanup()
        
        # Save settings
        self.settings.sync()
        
        # Hide tray icon before quitting
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        
        # Actually quit the application
        QApplication.quit()

    def show_prompt_dialog(self):
        dialog = SystemPromptDialog(self, self.prompt_manager)
        dialog.exec()

    def position_window_on_screen(self):
        """Position the window on the current screen, with Wayland multiscreen support."""
        # Get the screen where the cursor is
        cursor_pos = QCursor().pos()
        screens = QGuiApplication.screens()
        
        # Default to primary screen
        target_screen = QGuiApplication.primaryScreen()
        
        # Find the screen containing the cursor
        for screen in screens:
            if screen.geometry().contains(cursor_pos):
                target_screen = screen
                break
        
        # Get available geometry (accounts for taskbars/panels)
        available_geometry = target_screen.availableGeometry()
        
        # Position window in the center of the available area
        window_width = self.width()
        window_height = self.height()
        
        x = available_geometry.x() + (available_geometry.width() - window_width) // 2
        y = available_geometry.y() + (available_geometry.height() - window_height) // 2
        
        self.setGeometry(x, y, window_width, window_height)
        
        # Save the current screen for future reference
        self.current_screen = target_screen
        
        # Check for Wayland environment and apply specific adjustments
        self.detect_wayland_environment()
        
    def detect_wayland_environment(self):
        """Detect if running on Wayland and apply specific adjustments."""
        # Check if running on Wayland using platform name and configuration
        platform_name = QGuiApplication.platformName()
        is_wayland_platform = platform_name.lower() == "wayland"
        
        # Use config class to check if Wayland is enabled/detected
        is_wayland_enabled = False
        if self.config and hasattr(self.config, 'is_wayland_enabled'):
            is_wayland_enabled = self.config.is_wayland_enabled()
        
        is_wayland = is_wayland_platform or is_wayland_enabled
        
        if is_wayland:
            logger.info(f"Wayland environment detected: Platform={platform_name}")
            # Apply Wayland-specific settings
            self.apply_wayland_settings()
            
            # Connect to screen added/removed signals if available
            for screen in QGuiApplication.screens():
                self.monitor_screen_changes(screen)
                
            # Debug screen information if enabled
            if self.config and self.config.get("wayland", "debug_screen_info", False):
                self.log_screen_info()
        else:
            logger.info(f"Non-Wayland environment detected: {platform_name}")
    
    def log_screen_info(self):
        """Log detailed information about all available screens."""
        screens = QGuiApplication.screens()
        primary = QGuiApplication.primaryScreen()
        
        logger.info(f"Number of screens: {len(screens)}")
        logger.info(f"Primary screen: {primary.name()}")
        
        for i, screen in enumerate(screens):
            logger.info(f"Screen {i+1}: {screen.name()}")
            logger.info(f"  - Size: {screen.size().width()}x{screen.size().height()}")
            logger.info(f"  - Geometry: {screen.geometry().x()},{screen.geometry().y()} {screen.geometry().width()}x{screen.geometry().height()}")
            logger.info(f"  - Available: {screen.availableGeometry().x()},{screen.availableGeometry().y()} {screen.availableGeometry().width()}x{screen.availableGeometry().height()}")
            logger.info(f"  - DPI: {screen.logicalDotsPerInch()}")
            logger.info(f"  - Scale Factor: {screen.devicePixelRatio()}")
            logger.info(f"  - Depth: {screen.depth()} bits")
            logger.info(f"  - Is Primary: {screen == primary}")
            
    def apply_wayland_settings(self):
        """Apply Wayland-specific settings."""
        # Enable Qt Wayland specific settings if available
        try:
            # Use settings from config if available
            if self.config:
                # Set Qt environment variable via QSettings if needed
                if self.config.get("wayland", "disable_window_decoration", True):
                    self.settings.setValue("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
                
                # Apply scale factor if configured
                scale_factor = self.config.get_wayland_scale_factor() if hasattr(self.config, 'get_wayland_scale_factor') else 0
                if scale_factor > 0 and scale_factor != 1.0:
                    logger.info(f"Applying Wayland scale factor: {scale_factor}")
                    # Note: This is only for reference, as scaling must be done via env vars before app starts
                
                # Set window flags for Wayland
                if self.config.get("wayland", "stay_on_top", False):
                    self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
                
                # Handle maximize to active screen preference
                if self.config.get("wayland", "maximize_to_active_screen", True):
                    logger.info("Window will maximize to active screen")
            
            # Adjust for high DPI screens
            if self.current_screen and self.current_screen.logicalDotsPerInch() > 120:
                self.adjustForHighDPI()
                
            # Log Wayland configuration
            logger.info("Applied Wayland-specific settings")
        except Exception as e:
            logger.error(f"Error applying Wayland settings: {e}")
            
    def monitor_screen_changes(self, screen):
        """Monitor screen changes for Wayland multi-monitor setup."""
        try:
            # Connect to screen geometry or availability changes if signals exist
            # Note: QScreen signals may vary by Qt version and platform
            if hasattr(screen, 'geometryChanged'):
                screen.geometryChanged.connect(self.on_screen_geometry_changed)
            if hasattr(screen, 'availableGeometryChanged'):
                screen.availableGeometryChanged.connect(self.on_screen_available_geometry_changed)
            
            logger.info(f"Monitoring screen changes for: {screen.name()}")
        except Exception as e:
            logger.error(f"Error setting up screen monitoring: {e}")
    
    def on_screen_geometry_changed(self, geometry):
        """Handle screen geometry changes."""
        logger.info(f"Screen geometry changed: {geometry}")
        
        # Check if the current window is on this screen and reposition if needed
        current_geometry = self.geometry()
        if geometry.intersects(current_geometry):
            # Adjust window position to stay within the new screen geometry
            self.reposition_window_for_geometry(geometry)
    
    def on_screen_available_geometry_changed(self, geometry):
        """Handle changes in available screen geometry (e.g., panel size changes)."""
        logger.info(f"Available screen geometry changed: {geometry}")
        
        # Only reposition if this is our current screen
        if self.current_screen and self.current_screen.availableGeometry() == geometry:
            self.reposition_window_for_geometry(geometry)
    
    def reposition_window_for_geometry(self, geometry):
        """Reposition the window to fit within the given geometry."""
        current_geometry = self.geometry()
        
        # Check if window is now outside screen boundaries
        if not geometry.contains(current_geometry):
            # Keep the window size but adjust position
            new_x = max(geometry.x(), min(current_geometry.x(), 
                                         geometry.x() + geometry.width() - current_geometry.width()))
            new_y = max(geometry.y(), min(current_geometry.y(),
                                         geometry.y() + geometry.height() - current_geometry.height()))
            
            self.setGeometry(new_x, new_y, current_geometry.width(), current_geometry.height())
            logger.info(f"Repositioned window to: {new_x},{new_y}")
    
    def adjustForHighDPI(self):
        """Adjust UI elements for high DPI screens."""
        # Get current screen DPI
        dpi = self.current_screen.logicalDotsPerInch()
        scale_factor = dpi / 96.0  # Standard DPI is typically 96
        
        # Only adjust if scale factor is significant
        if scale_factor > 1.2:
            logger.info(f"Adjusting for high DPI screen: {dpi} DPI, scale factor: {scale_factor:.2f}")
            
            # Adjust font sizes
            base_font_size = int(self.config.get("ui", "font_size", 14))
            adjusted_size = max(base_font_size, int(base_font_size * scale_factor))
            
            # Update fonts
            font = QFont(self.config.get("ui", "font_family", "Inter"), adjusted_size)
            self.setFont(font)
            
            # You could also adjust icon sizes, layout spacing, etc.
            # self.container.setStyleSheet(f"QWidget#container {{ padding: {int(12 * scale_factor)}px; }}")

    def on_screen_added(self, screen):
        """Handle a new screen being added to the system."""
        logger.info(f"New screen added: {screen.name()}")
        
        # Update our list of screens
        self.screens_list = QGuiApplication.screens()
        
        # Set up monitoring for this screen
        self.monitor_screen_changes(screen)
        
        # If this is the first screen or we're on a virtual desktop,
        # we might want to reposition the window
        if len(self.screens_list) == 1 or not self.current_screen:
            self.position_window_on_screen()
    
    def on_screen_removed(self, screen):
        """Handle a screen being removed from the system."""
        logger.info(f"Screen removed: {screen.name()}")
        
        # Update our list of screens
        self.screens_list = QGuiApplication.screens()
        
        # If our current screen was removed, reposition to a new screen
        if self.current_screen == screen:
            logger.info("Current screen was removed, repositioning window")
            self.current_screen = None
            self.position_window_on_screen()
            
    def showEvent(self, event):
        """Handle window show event."""
        super().showEvent(event)
        
        # Ensure proper positioning on the current screen when shown
        # This is especially important for Wayland
        self.position_window_on_screen()
        
    def resizeEvent(self, event):
        """Handle window resize events."""
        super().resizeEvent(event)
        
        # Update window layout if needed
        # This is especially important for maintaining correct appearance on Wayland
        
        # Check if we're within screen boundaries after resize
        if self.current_screen:
            screen_geom = self.current_screen.availableGeometry()
            window_geom = self.geometry()
            
            # Ensure window is not larger than screen
            if window_geom.width() > screen_geom.width() or window_geom.height() > screen_geom.height():
                new_width = min(window_geom.width(), screen_geom.width())
                new_height = min(window_geom.height(), screen_geom.height())
                self.resize(new_width, new_height)