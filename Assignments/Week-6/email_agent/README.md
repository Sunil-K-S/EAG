# Agentic Email Assistant

## Architecture Overview

### 1. Perception Layer
- **Input Processing**: Handles raw user input and preferences
- **Context Understanding**: Maintains conversation context
- **Preference Management**: Collects, stores, and applies user preferences to emails
- **Intent Recognition**: Determines user goals and requirements
- **Function Call Formatting**: Ensures proper formatting of API calls
- **LLM Integration**: Manages interactions with the Gemini model
- **Validation**: Validates email requests and formats

### 2. Memory Layer
- **Short-term Memory**: Stores current conversation context
- **Preference Storage**: Maintains user preferences in JSON format
- **Context Management**: Tracks function execution status
- **History Management**: Stores conversation and function call history
- **Result Tracking**: Captures and stores results from function calls
- **State Persistence**: Saves and shares execution state between components

### 3. Decision Layer
- **Action Selection**: Chooses appropriate functions based on LLM responses
- **Preference Integration**: Incorporates user preferences into decisions
- **JSON Extraction**: Extracts structured function calls from LLM responses
- **Parameter Validation**: Validates and cleans function parameters
- **Verification**: Tracks completion status of functions
- **Error Recovery**: Handles and recovers from execution errors

### 4. Action Layer
- **Tool Execution**: Calls MCP API functions with proper formatting
- **Parameter Formatting**: Formats input parameters according to API requirements
- **Preference Application**: Applies user preferences to email formatting
- **Response Formatting**: Processes API responses for readability
- **Error Handling**: Manages API execution errors
- **Result Extraction**: Extracts and formats relevant results

## Data Models

### 1. User Preferences
```python
class UserPreferences(BaseModel):
    language: str = "en"              # User's preferred language (en, fr, es)
    priority: str = "normal"          # Email priority (low, normal, high)
    email_format: str = "html"        # Preferred email format (plain, html)
    verification_level: str = "standard"  # Verification level (basic, standard, strict)
```

### 2. Tool Responses
```python
class TextResponse(BaseModel):
    content: TextContent
    
class EmailResponse(BaseModel):
    message_id: str
    to: str
    subject: str
    status: str
```

## System Flow

1. **Preference Collection**
   - Initial preferences collected during system startup
   - Loaded from preferences.json if available
   - User can modify preferences through interactive prompts
   - Preferences stored for future sessions

2. **Task Execution**
   - Problem statement parsed and analyzed
   - LLM generates sequence of function calls
   - Decision layer extracts and validates function calls
   - Action layer executes functions with proper parameters
   - Results stored and tracked for future steps

3. **Email Formatting**
   - User preferences applied to email content
   - HTML formatting applied based on preference
   - Language tags added to subject based on preference
   - Priority-based styling applied to content
   - Formatting applied in the action layer before API call

4. **System Feedback Loop**
   - Results from each function saved to memory
   - State information passed to LLM for next decisions
   - Function execution status tracked to prevent duplication
   - Detailed information about calculation results provided to LLM

## Key Features

### 1. User Preference Application
- **Language Support**: Subject prefixed with language code (e.g., [ES] for Spanish)
- **Email Format**: Plain text converted to HTML when preferred
- **Priority Styling**: Email color and formatting based on priority level
- **Cached Preferences**: Preferences loaded once and cached for performance

### 2. Dynamic Function Handling
- **No Hardcoded Functions**: System discovers available functions at runtime
- **Parameter Validation**: Function parameters cleaned and validated before execution
- **Proper API Formatting**: Parameters formatted according to MCP API requirements
- **Result Tracking**: Function results stored by key for future reference

### 3. Error Handling and Recovery
- **Error Detection**: Failed functions tracked separately
- **Recovery Mechanisms**: Functions can be retried after failure
- **Parameter Cleaning**: Invalid parameters removed before API calls
- **Mock Email Support**: Emails can be "sent" even without Gmail credentials

### 4. LLM Guidance
- **Context Management**: LLM provided with full execution context
- **Result Sharing**: Calculation results explicitly shared with LLM
- **Status Tracking**: LLM informed of completed and failed functions
- **Format Guidance**: LLM instructed on proper function call formats

## Implementation Notes

### Preference Integration
The system applies user preferences in the Action layer, specifically in the `act` function within `action.py`. Preferences affect:

1. **Email Format**: Converts plain text to HTML based on the `email_format` preference
2. **Language**: Adds language prefix to subject line based on the `language` preference
3. **Priority**: Applies color styling based on the `priority` preference
4. **Email Metadata**: Includes preference information in email footer

### MCP API Integration
The system interfaces with the MCP API through:

1. **Input Formatting**: Wraps parameters in `input_data` field as required by API
2. **Parameter Cleaning**: Removes non-essential fields like "verification" and "reasoning"
3. **Response Parsing**: Extracts and processes JSON responses from the API
4. **Error Handling**: Manages API errors and timeouts gracefully

## Example Email with Applied Preferences

For a Spanish user with high priority and HTML format preferences:

```
Subject: [ES] Resultado del cálculo exponencial

<html>
<body>
    <div style="font-family: Arial, sans-serif; color: #CC0000;">
        <h2>Email Agent Result</h2>
        <p>La suma de los exponenciales de los valores ASCII de 'INDIA' es 7.5998222460930797959560504664225905547098797815855e+33</p>
        <hr>
        <p style="font-size: 12px; color: #666666;">
            Sent by Email Agent<br>
            Language: es<br>
            Priority: high
        </p>
    </div>
</body>
</html>
```

## Command-Line Usage

```bash
python main.py
```

At startup, the system will:
1. Prompt for user preferences if not already saved
2. Connect to the MCP server
3. Process the task step by step
4. Apply preferences to email formatting
5. Display detailed progress information 