# OpenHands Software Agent SDK - Complete Reference

## Installation

```bash
pip install openhands-sdk        # Core SDK (openhands.sdk)
pip install openhands-tools      # Built-in tools (openhands.tools)
pip install openhands-workspace  # Optional: for sandboxed workspaces
pip install openhands-agent-server  # Optional: for remote agent server
```

---

## Core Classes

### 1. LLM - Language Model Configuration

```python
from openhands.sdk import LLM
from pydantic import SecretStr

llm = LLM(
    model="anthropic/claude-sonnet-4-5-20250929",  # or "openhands/claude-sonnet-4-5-20250929"
    api_key=SecretStr(os.getenv("LLM_API_KEY")),
    usage_id="agent",           # Optional: for tracking
    temperature=0.7,            # Optional
    max_tokens=4096,            # Optional
    base_url=None,              # Optional: custom API endpoint
)

# Access metrics
print(f"Cost: ${llm.metrics.accumulated_cost}")
print(f"Tokens: {llm.metrics.accumulated_tokens}")
```

### 2. Agent - The AI Agent

```python
from openhands.sdk import Agent
from openhands.sdk.tool import Tool

agent = Agent(
    llm=llm,
    tools=[
        Tool(name="terminal"),
        Tool(name="file_editor"),
        Tool(name="task_tracker"),
    ],
    system_prompt="Optional custom system prompt",
    agent_context=agent_context,     # Optional: skills and context
    mcp_config=mcp_config,           # Optional: MCP server integration
    filter_tools_regex="...",        # Optional: filter available tools
)
```

### 3. Conversation - Interaction Manager

```python
from openhands.sdk import Conversation

conversation = Conversation(
    agent=agent,
    workspace="/path/to/workspace",   # or Workspace object
    callbacks=[event_callback],       # Optional: event listeners
    persistence_dir="/tmp/convs",     # Optional: save/resume sessions
    conversation_id="my-session-001", # Optional: for resuming
)

# Send messages and run
conversation.send_message("Your task here")
conversation.run()

# Continue conversation
conversation.send_message("Follow-up task")
conversation.run()

# Access state
print(f"ID: {conversation.state.id}")
print(f"Status: {conversation.state.execution_status}")
print(f"Events: {len(conversation.state.events)}")

# Generate title
title = conversation.generate_title(max_length=60, llm=title_gen_llm)

# Cleanup
conversation.close()
```

### 4. Workspace - Execution Environment

```python
from openhands.sdk import Workspace

# Local workspace (default)
conversation = Conversation(agent=agent, workspace="/path/to/project")

# Remote workspace (via agent server)
workspace = Workspace(host="http://localhost:8000")
result = workspace.execute_command("pwd")
print(f"Exit code: {result.exit_code}")
print(f"Output: {result.stdout}")

conversation = Conversation(agent=agent, workspace=workspace)
```

### 5. Tool - Tool Specification

```python
from openhands.sdk.tool import Tool

# Reference built-in tools by name
tools = [
    Tool(name="terminal"),
    Tool(name="file_editor"),
    Tool(name="task_tracker"),
    Tool(name="my_custom_tool"),  # Custom registered tool
]

# With parameters
tools = [
    Tool(name="terminal", params={"working_dir": "/workspace"}),
    Tool(name="task_tracker", params={"save_dir": "/workspace"}),
]
```

---

## Built-in Tools

### TerminalTool - Bash Execution

```python
from openhands.tools.terminal import TerminalTool

# Name: "terminal"
# Capabilities:
# - Execute bash commands
# - Persistent shell session
# - Environment variables persist
# - Soft timeout with continuation
# - Background processes
# - Input to running processes (C-c, C-d, C-z)
```

### FileEditorTool - File Operations

```python
from openhands.tools.file_editor import FileEditorTool

# Name: "file_editor"
# Capabilities:
# - Create, read, edit files
# - Advanced editing with diff-based modifications
# - View file contents
# - Search and replace
```

### TaskTrackerTool - Task Management

```python
from openhands.tools.task_tracker import TaskTrackerTool

# Name: "task_tracker"
# Capabilities:
# - Organize development tasks
# - Track progress
# - Save to workspace
```

### BrowserToolSet - Web Browsing (GUI only)

```python
from openhands.tools.browser import BrowserToolSet

# Disabled in CLI mode via cli_mode=True
# Capabilities:
# - Automate web interactions
# - Navigate pages
# - Extract content
```

---

## Default Agent Preset

```python
from openhands.sdk import LLM, Conversation
from openhands.tools.preset.default import get_default_agent

llm = LLM(
    model="openhands/claude-sonnet-4-5-20250929",
    api_key=os.getenv("LLM_API_KEY"),
)

# Pre-configured agent with common tools
agent = get_default_agent(
    llm=llm,
    cli_mode=True,  # Disable browser tools for CLI
)

# Includes:
# - TerminalTool (bash execution)
# - FileEditorTool (file operations)
# - TaskTrackerTool (task management)
# - Built-in tools (Finish, Think)
```

---

## Custom Tool Creation

### Step 1: Define Action Schema (Input)

```python
from pydantic import Field
from openhands.sdk import Action

class MyToolAction(Action):
    param1: str = Field(description="First parameter")
    param2: int = Field(default=10, description="Optional parameter")
    param3: str | None = Field(default=None, description="Optional nullable")
```

### Step 2: Define Observation Schema (Output)

```python
from openhands.sdk import Observation

class MyToolObservation(Observation):
    success: bool = Field(description="Whether operation succeeded")
    result: str = Field(default="", description="Result data")
    error: str | None = Field(default=None, description="Error message")
```

### Step 3: Create Executor

```python
from openhands.sdk.tool import ToolExecutor

class MyToolExecutor(ToolExecutor[MyToolAction, MyToolObservation]):
    def __init__(self, config_value: str):
        self.config_value = config_value

    def __call__(self, action: MyToolAction, conversation=None) -> MyToolObservation:
        try:
            # Your tool logic here
            result = f"Processed: {action.param1}"
            return MyToolObservation(success=True, result=result)
        except Exception as e:
            return MyToolObservation(success=False, error=str(e))
```

### Step 4: Define ToolDefinition with Factory

```python
from collections.abc import Sequence
from openhands.sdk import ToolDefinition
from openhands.sdk.tool import ToolAnnotations

class MyTool(ToolDefinition[MyToolAction, MyToolObservation]):
    name = "my_tool"  # Class attribute for registration

    @classmethod
    def create(
        cls,
        conv_state,  # ConversationState
        config_value: str = "default",
        executor: ToolExecutor | None = None,
    ) -> Sequence["MyTool"]:
        if executor is None:
            executor = MyToolExecutor(config_value=config_value)

        return [cls(
            description="Description of what the tool does",
            action_type=MyToolAction,
            observation_type=MyToolObservation,
            executor=executor,
            annotations=ToolAnnotations(
                title="My Tool",
                readOnlyHint=True,       # Doesn't modify state
                destructiveHint=False,   # Not destructive
                idempotentHint=True,     # Same input = same output
                openWorldHint=False,     # Doesn't access external resources
            ),
        )]
```

### Step 5: Register Tool

```python
from openhands.sdk.tool import register_tool

register_tool(MyTool.name, MyTool)
# or
register_tool("my_tool", MyTool)
```

### Step 6: Use Custom Tool

```python
from openhands.sdk import Agent
from openhands.sdk.tool import Tool

agent = Agent(
    llm=llm,
    tools=[
        Tool(name="terminal"),
        Tool(name="file_editor"),
        Tool(name="my_tool"),  # Your custom tool
    ],
)
```

---

## Skills and Agent Context

### Define Skills

```python
from openhands.sdk import AgentContext
from openhands.sdk.context import Skill, KeywordTrigger

agent_context = AgentContext(
    skills=[
        # Always-active skill
        Skill(
            name="repo_guidelines.md",
            content="""
# Repository Guidelines
- Always run tests before committing
- Follow PEP 8 style guidelines
""",
            trigger=None,  # Always active
        ),

        # Keyword-triggered skill
        Skill(
            name="deployment_guide.md",
            content="""
# Deployment Instructions
1. Run `make build`
2. Run `make deploy`
""",
            trigger=KeywordTrigger(keywords=["deploy", "deployment", "release"]),
        ),
    ],
    system_message_suffix="\n\nAlways be thorough and ask for clarification.",
)

agent = Agent(
    llm=llm,
    tools=[...],
    agent_context=agent_context,
)
```

---

## MCP Integration

```python
from openhands.sdk import Agent
from openhands.sdk.tool import Tool

# Configure MCP servers
mcp_config = {
    "mcpServers": {
        "fetch": {
            "command": "uvx",
            "args": ["mcp-server-fetch"]
        },
        "repomix": {
            "command": "npx",
            "args": ["-y", "repomix@1.4.2", "--mcp"]
        },
    }
}

agent = Agent(
    llm=llm,
    tools=[
        Tool(name="terminal"),
        Tool(name="file_editor"),
    ],
    mcp_config=mcp_config,
    # Optional: filter MCP tools
    filter_tools_regex="^(?!repomix)(.*)|^repomix.*pack_codebase.*$",
)
```

---

## Event Callbacks

```python
from openhands.sdk import Event, LLMConvertibleEvent

# Storage for events
all_events = []
llm_messages = []

def event_callback(event: Event):
    all_events.append(event)
    if isinstance(event, LLMConvertibleEvent):
        llm_messages.append(event.to_llm_message())
        print(f"Event: {type(event).__name__}")

conversation = Conversation(
    agent=agent,
    workspace=workspace,
    callbacks=[event_callback],
)

# Async callback support
from openhands.sdk.utils.async_utils import AsyncCallbackWrapper

async def async_callback(event: Event):
    await asyncio.sleep(0)  # Async operations
    print(f"Async event: {type(event).__name__}")

# Use with AsyncCallbackWrapper
conversation = Conversation(
    agent=agent,
    workspace=workspace,
    callbacks=[AsyncCallbackWrapper(async_callback)],
)
```

---

## Conversation Persistence

```python
# Save conversation for later
conversation = Conversation(
    agent=agent,
    workspace=workspace,
    persistence_dir="/tmp/openhands_conversations",
    conversation_id="my-project-session-001",
)

conversation.send_message("Create a module")
conversation.run()

# Later, resume the conversation
resumed = Conversation(
    agent=agent,
    workspace=workspace,
    persistence_dir="/tmp/openhands_conversations",
    conversation_id="my-project-session-001",  # Same ID resumes
)
# Conversation context is restored
```

---

## Agent Server (REST API)

### Start Server

```bash
python -m openhands.agent_server --port 8000 --host 127.0.0.1
```

### REST API Endpoints

```bash
# Create conversation
POST /api/conversations

# Send message
POST /api/conversations/{id}/events

# Run conversation
POST /api/conversations/{id}/run

# Get state
GET /api/conversations/{id}

# Search events
GET /api/conversations/{id}/events/search?limit=10

# Pause
POST /api/conversations/{id}/pause

# Generate title
POST /api/conversations/{id}/generate_title

# List conversations
GET /api/conversations/search?limit=20&sort_by=UPDATED_AT_DESC

# Delete
DELETE /api/conversations/{id}
```

### Python Client for Remote Server

```python
from openhands.sdk import Workspace, Conversation

# Connect to remote workspace
workspace = Workspace(host="http://localhost:8000")

# Test connection
result = workspace.execute_command("pwd")
print(result.stdout)

# Create conversation
conversation = Conversation(
    agent=agent,
    workspace=workspace,
    callbacks=[event_callback],
)

conversation.send_message("Task description")
conversation.run()
```

---

## Complete Example

```python
import os
from pydantic import SecretStr
from openhands.sdk import LLM, Agent, Conversation, Tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool

# 1. Configure LLM
llm = LLM(
    model="anthropic/claude-sonnet-4-5-20250929",
    api_key=SecretStr(os.getenv("ANTHROPIC_API_KEY")),
)

# 2. Create Agent with tools
agent = Agent(
    llm=llm,
    tools=[
        Tool(name=TerminalTool.name),
        Tool(name=FileEditorTool.name),
        Tool(name=TaskTrackerTool.name),
    ],
    system_prompt="You are a helpful coding assistant.",
)

# 3. Create Conversation
conversation = Conversation(
    agent=agent,
    workspace=os.getcwd(),
)

# 4. Send message and run
conversation.send_message("Write a Python script that prints 'Hello, World!'")
conversation.run()

# 5. Continue conversation
conversation.send_message("Now add a function that greets by name.")
conversation.run()

# 6. Access metrics
print(f"Total cost: ${llm.metrics.accumulated_cost}")
print(f"Total tokens: {llm.metrics.accumulated_tokens}")

# 7. Cleanup
conversation.close()
```

---

## Sources

- [OpenHands Software Agent SDK - GitHub](https://github.com/OpenHands/software-agent-sdk)
- [OpenHands SDK Documentation](https://docs.openhands.dev/sdk)
- [Getting Started Guide](https://docs.openhands.dev/sdk/getting-started)
- [Custom Tools Guide](https://docs.openhands.dev/sdk/guides/custom-tools)
- [Skills Guide](https://docs.openhands.dev/sdk/guides/skill)
- [MCP Integration](https://docs.openhands.dev/sdk/guides/mcp)
- [Agent Delegation](https://docs.openhands.dev/sdk/guides/agent-delegation)
