# Computer Agent Architecture

This document describes the architecture of the Computer Agent application, showing the relationships between different components and their responsibilities.

## Core Components

The application consists of the following core components:

### Config
- **Responsibility**: Centralized configuration management
- **Interfaces with**: All other components
- **Key features**:
  - Load/save configuration from/to file
  - Provide access to configuration values
  - Default configurations for all components

### Store
- **Responsibility**: State management and data flow
- **Interfaces with**: AnthropicClient, ComputerControl, UI
- **Key features**:
  - Manage application state
  - Process actions from AI
  - Execute actions on the computer
  - Update UI with results

### AnthropicClient
- **Responsibility**: Communication with Anthropic API
- **Interfaces with**: Store
- **Key features**:
  - Send requests to Anthropic API
  - Parse responses
  - Handle API errors

### ComputerControl
- **Responsibility**: Perform actions on the computer
- **Interfaces with**: Store
- **Key features**:
  - Control mouse and keyboard
  - Take screenshots
  - Map between AI and physical screen coordinates

### VoiceController
- **Responsibility**: Voice input and output
- **Interfaces with**: UI
- **Key features**:
  - Speech recognition
  - Text-to-speech
  - Wake word detection

### PromptManager
- **Responsibility**: Manage system prompts
- **Interfaces with**: AnthropicClient
- **Key features**:
  - Load/save prompts from/to file
  - Provide access to current prompt
  - Reset to default prompt

### UI (MainWindow)
- **Responsibility**: User interface
- **Interfaces with**: Store, VoiceController
- **Key features**:
  - Display agent actions and responses
  - Accept user input
  - Provide settings and controls

## Component Relationships

```
┌───────────────┐     ┌───────────────┐
│     Config    │◄────┤  All Components│
└───────┬───────┘     └───────────────┘
        │
        ▼
┌───────────────┐     ┌───────────────┐
│ AnthropicClient│◄────┤    Store      │
└───────┬───────┘     └───────┬───────┘
        │                     │
        ▼                     ▼
┌───────────────┐     ┌───────────────┐
│ PromptManager │     │ComputerControl│
└───────────────┘     └───────────────┘
                              ▲
                              │
┌───────────────┐     ┌───────────────┐
│VoiceController│◄────┤   MainWindow  │
└───────────────┘     └───────┬───────┘
                              │
                              ▼
                      ┌───────────────┐
                      │     User      │
                      └───────────────┘
```

## Data Flow

1. **User** inputs a task through the **MainWindow** (text or voice via **VoiceController**)
2. **MainWindow** passes the task to the **Store**
3. **Store** requests the next action from **AnthropicClient** (using prompt from **PromptManager**)
4. **AnthropicClient** returns the action to **Store**
5. **Store** executes the action using **ComputerControl**
6. **ComputerControl** performs the action and returns a screenshot
7. **Store** updates the **MainWindow** and sends the result back to **AnthropicClient**
8. This cycle continues until the task is complete or cancelled

## Error Handling

- **Config**: Handles file I/O errors, uses defaults when needed
- **AnthropicClient**: Handles API errors, retries, rate limits
- **ComputerControl**: Handles action failures gracefully
- **Store**: Handles errors from all components, provides recovery options
- **MainWindow**: Displays errors to the user
- **VoiceController**: Handles speech recognition failures

## Configuration Flow

1. **Config** loads settings from file on startup
2. Each component receives its configuration from **Config**
3. UI settings changes update **Config**
4. **Config** saves changes to file

## Threading Model

- **MainWindow**: Runs on the main thread (UI thread)
- **AnthropicClient**: API calls run on a separate thread
- **ComputerControl**: Actions run on the main thread
- **VoiceController**: Recognition runs on a separate thread 