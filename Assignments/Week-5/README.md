# TSAI AI Agents - Session 5 Notes

## Key Topics Covered

### 1. UV Package Manager
- UV is a fast Python package manager and environment manager created by Astral
- Key features:
  - Lightning fast installations and dependency resolutions (up to 10-20x faster than pip)
  - Seamless virtual environment management with automatic creation
  - Automatic log file generation for reproducibility
  - Compatible with pip, project.toml and requirements.txt
  - Caching of wheels across environments for faster reinstalls
  - Can use packages without installation (one-time dependency) using `uv pip run`
- Installation: `pip install uv`
- Basic Commands:
  ```bash
  uv init my_project     # Initialize new project
  uv add package_name    # Install package
  uv pip compile        # Generate requirements.txt
  uv pip sync          # Install from requirements.txt
  ```
- References:
  - [UV Documentation](https://github.com/astral-sh/uv)
  - [UV vs pip Benchmarks](https://github.com/astral-sh/uv/blob/main/BENCHMARKS.md)

### 2. Understanding LLM Internal Logic
- Based on March 2024 research: "The Transformer Circuits Thread" and "On the Biology of Large Language Models"
- Key Findings:
  1. Early Layers (Input Processing):
     - Convert generic embeddings into context-specific meanings
     - Handle word disambiguation (e.g., "bank" as financial vs riverside)
  
  2. Middle Layers (Logic Circuits):
     - Mathematical operations (e.g., addition, multiplication)
     - Entity relationships and knowledge graphs
     - Language processing and grammar rules
     - Pattern recognition and rhyme selection
     - Planning and decision making
     - Medical diagnosis patterns
     - Language-independent semantic features

  3. Final Layers (Output Generation):
     - Plan execution
     - Token prediction
     - Response formatting

- References:
  - [Transformer Circuits Thread](https://transformer-circuits.pub/)
  - [On the Biology of LLMs](https://arxiv.org/abs/2403.07610)

### 3. Chain of Thought (CoT) Prompting
- Advanced prompting technique that improves reasoning by making thinking explicit
- Types:
  1. Zero-shot CoT:
     - Uses phrases like "Let's solve this step by step"
     - No examples needed
     - Example: "Let's approach this systematically..."

  2. Few-shot CoT:
     - Provides explicit examples of step-by-step reasoning
     - More reliable but requires more tokens
     - Example:
       ```
       Q: If John has 5 apples and eats 2, how many are left?
       A: Let's solve step by step:
       1. Start with 5 apples
       2. Subtract 2 apples eaten
       3. Therefore, 3 apples remain
       ```

- Benefits:
  - Makes output more interpretable
  - Useful for math, coding, logic, ethics, and legal reasoning
  - Activates internal reasoning patterns in the model
  - Reduces hallucination through explicit reasoning

- References:
  - [Chain of Thought Paper](https://arxiv.org/abs/2201.11903)
  - [Language Models Step-by-Step](https://arxiv.org/abs/2305.20050)

### 4. ReAct Framework (Reasoning + Acting)
- Combines Chain of Thought reasoning with tool usage
- Key Components:
  1. Reasoning: Internal step-by-step thinking
  2. Acting: External tool/API calls
  3. Observation: Processing tool outputs
  4. Reflection: Evaluating results and planning next steps

- Implementation Pattern:
  ```python
  while not task_complete:
      # Reasoning
      thought = model.think(context)
      
      # Acting
      action = model.decide_action(thought)
      result = execute_action(action)
      
      # Observation
      observation = process_result(result)
      
      # Reflection
      context = update_context(thought, action, observation)
  ```

- References:
  - [ReAct Paper](https://arxiv.org/abs/2210.03629)
  - [ReAct: Synergizing Reasoning and Acting in Language Models](https://react-lm.github.io/)

### 5. Structured Prompting
- Advanced prompting techniques for reliable outputs
- Key Components:
  1. Input-Output Format Templates:
     ```
     Input: <specific format>
     Output: <expected structure>
     ```
  
  2. Step-Labeled Reasoning:
     ```
     Step 1: <specific action>
     Step 2: <next action>
     ...
     ```
  
  3. Function-like Structuring:
     ```json
     {
       "function": "calculate",
       "parameters": {
         "operation": "add",
         "numbers": [2, 3]
       }
     }
     ```
  
  4. Goal Decomposition:
     - Break complex tasks into subtasks
     - Handle dependencies between subtasks
     - Validate intermediate results

- References:
  - [Structured Prompting](https://arxiv.org/abs/2302.00618)
  - [Prompt Engineering Guide](https://www.promptingguide.ai/)

## Assignment Details

### Task
1. Take the email assignment from Week-5 and enhance it with:
   - Structured prompting
   - Chain of thought reasoning
   - ReAct framework implementation
   - JSON-based function calls
   - Verification and self-check mechanisms

2. Validate and improve the prompt using ChatGPT with provided criteria:
   ```
   You're a prompt evaluation assistant. Review this prompt for:
   1. Explicit reasoning instructions
   2. Structured output format
   3. Separation of reasoning and tools
   4. Conversation loop support
   5. Instructional framing
   6. Self-check mechanisms
   7. Reasoning type awareness
   8. Fallback options
   9. Overall clarity
   ```

3. Code Implementation Requirements:
   - JSON Structure Example:
     ```json
     {
       "function": "send_email",
       "parameters": {
         "to": "recipient@email.com",
         "subject": "Test",
         "body": "Content"
       },
       "verification": {
         "type": "email_validation",
         "checks": ["format", "domain", "content"]
       }
     }
     ```
   
   - Verification Steps:
     1. Input validation
     2. Tool execution verification
     3. Output validation
     4. Self-check by LLM
   
   - Error Handling:
     1. Invalid inputs
     2. Tool failures
     3. Verification failures
     4. Recovery strategies

### Evaluation Criteria
- Complexity: Minimum 5 distinct steps in email processing
- Prompt Structure: Clear, structured, with proper CoT
- Verification: Comprehensive checks at each step
- JSON Handling: Proper schema and validation
- Code Organization: Clean, modular, well-documented

### Resources
- Sample Code: Available in session repository
- Prompt Template: In session materials
- JSON Schema: RFC 8259 compliant
- Verification Examples: In session code 

# Week 5 Assignment: Email Processing System

## Usage

1. **Send Email**:
```python
await send_email(
    to_email="recipient@example.com",
    subject="Email Subject",
    body="Email Body",
    image_path="optional/path/to/image.png"
)
```

2. **Calculate Exponential Sum**:
```python
result = calculate_exponential_sum([73, 78, 68, 73, 65])
```

3. **Get ASCII Values**:
```python
values = get_ascii_values("INDIA")
```

## Error Handling

The system implements comprehensive error handling:
- Custom exceptions for different error types
- Proper logging of errors
- Retry mechanisms for failed operations
- User-friendly error messages
