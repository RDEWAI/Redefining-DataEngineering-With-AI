"""Base agent class for OpenHands-based PWI agents.

This module provides the foundation for all PWI agents using the OpenHands SDK.
It adapts the OpenHands Agent interface to work with PWI's domain-specific needs.
"""

from __future__ import annotations

import json
from abc import abstractmethod
from pathlib import Path
from typing import Any

from litellm import ChatCompletionToolParam
from pydantic import BaseModel, Field

from pwi.openhands.tools import get_registry, get_tools_for_agent
from pwi.utils.logging import get_logger

logger = get_logger("openhands.agents.base")


class PWIAgentConfig(BaseModel):
    """Configuration for a PWI OpenHands agent."""

    name: str
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 4096
    prompts_dir: Path | None = None


class PWIAgentState(BaseModel):
    """State for a PWI agent execution."""

    session_id: str
    business_request: str
    artifacts: dict[str, str] = Field(default_factory=dict)
    tool_outputs: list[dict[str, Any]] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    current_step: int = 0
    max_steps: int = 15  # Agents should complete efficiently in fewer steps
    is_complete: bool = False
    error: str | None = None
    called_tools: list[str] = Field(default_factory=list)  # Track tool calls to prevent duplicates
    max_unique_tool_calls: int = 10  # Force artifact generation after this many unique calls


class PWIAgentResult(BaseModel):
    """Result from a PWI agent execution."""

    success: bool
    artifact_type: str | None = None
    artifact_content: str | None = None
    artifact_format: str = "markdown"
    error_message: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""

    @classmethod
    def success_result(
        cls,
        artifact_type: str,
        artifact_content: str,
        artifact_format: str,
        model: str,
        tool_calls: list[dict[str, Any]] | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> PWIAgentResult:
        """Create a successful result."""
        return cls(
            success=True,
            artifact_type=artifact_type,
            artifact_content=artifact_content,
            artifact_format=artifact_format,
            model=model,
            tool_calls=tool_calls or [],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    @classmethod
    def failure_result(cls, error_message: str) -> PWIAgentResult:
        """Create a failure result."""
        return cls(
            success=False,
            error_message=error_message,
        )


class BasePWIAgent:
    """Base class for OpenHands-based PWI agents.

    This class provides the foundation for domain-specific agents that:
    - Use tools to interact with external systems (DuckDB, files, APIs)
    - Generate structured artifacts (DRD, PAD, DMD, etc.)
    - Work within the PWI workflow orchestration

    Subclasses must define:
    - AGENT_NAME: Unique identifier for the agent
    - ARTIFACT_TYPE: Type of artifact produced
    - ARTIFACT_FORMAT: Format of the artifact (markdown, csv, yaml)
    - get_required_inputs(): List of required artifacts from previous agents
    """

    # Class attributes to be defined by subclasses
    AGENT_NAME: str = "base"
    ARTIFACT_TYPE: str = "artifact"
    ARTIFACT_FORMAT: str = "markdown"
    VERSION: str = "1.0"

    def __init__(
        self,
        config: PWIAgentConfig,
        llm_client: Any = None,
    ) -> None:
        """Initialize the PWI agent.

        Args:
            config: Agent configuration.
            llm_client: LLM client for completions (optional, can be injected).
        """
        self.config = config
        self.llm = llm_client
        self._system_prompt: str | None = None
        self._tools: list[ChatCompletionToolParam] | None = None
        self._registry = get_registry()

    @property
    def tools(self) -> list[ChatCompletionToolParam]:
        """Get the tools available to this agent."""
        if self._tools is None:
            self._tools = get_tools_for_agent(self.AGENT_NAME)
        return self._tools

    @property
    def tool_names(self) -> list[str]:
        """Get names of available tools."""
        return [t["function"]["name"] for t in self.tools]

    def _load_system_prompt(self) -> str:
        """Load the system prompt for this agent.

        Returns:
            The system prompt string.
        """
        # Try to load from prompts directory
        if self.config.prompts_dir:
            prompt_file = self.config.prompts_dir / f"{self.AGENT_NAME}.md"
            if prompt_file.exists():
                return prompt_file.read_text(encoding="utf-8")

        # Fall back to default prompt
        return self._get_default_prompt()

    @property
    def system_prompt(self) -> str:
        """Get the system prompt, loading from file if needed."""
        if self._system_prompt is None:
            self._system_prompt = self._load_system_prompt()
        return self._system_prompt

    @abstractmethod
    def _get_default_prompt(self) -> str:
        """Get the default system prompt for this agent.

        Subclasses must implement this to provide a fallback prompt.
        """
        pass

    @abstractmethod
    def get_required_inputs(self) -> list[str]:
        """Return list of required artifact types from previous agents.

        Returns:
            List of artifact type strings (e.g., ['drd']).
        """
        pass

    def _build_context(self, state: PWIAgentState) -> str:
        """Build the context string from state.

        Args:
            state: Current agent state with request and artifacts.

        Returns:
            Context string to include in the prompt.
        """
        parts = []

        # Add the business request
        parts.append("## Business Request\n")
        parts.append(state.business_request)
        parts.append("\n")

        # Add artifacts from previous agents
        for artifact_type in self.get_required_inputs():
            if artifact_type in state.artifacts:
                parts.append(f"\n## {artifact_type.upper()} (from previous agent)\n")
                parts.append(state.artifacts[artifact_type])
                parts.append("\n")

        # Add tool outputs if any
        if state.tool_outputs:
            parts.append("\n## Tool Outputs\n")
            for output in state.tool_outputs:
                tool_name = output.get("tool", "unknown")
                result = output.get("result", {})
                parts.append(f"\n### {tool_name}\n```json\n{json.dumps(result, indent=2)}\n```\n")

        return "\n".join(parts)

    def _build_messages(self, state: PWIAgentState) -> list[dict[str, Any]]:
        """Build the message list for LLM completion.

        Args:
            state: Current agent state.

        Returns:
            List of messages for the LLM.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]

        # Add any existing messages from the state
        messages.extend(state.messages)

        # If no user messages yet, add the initial prompt
        if not any(m["role"] == "user" for m in state.messages):
            context = self._build_context(state)
            user_message = self._build_user_message(context)
            messages.append({"role": "user", "content": user_message})

        return messages

    def _build_user_message(self, context: str) -> str:
        """Build the user message from context.

        Args:
            context: Context string with request and artifacts.

        Returns:
            User message for the LLM.
        """
        return f"""Please analyze the following and generate the {self.ARTIFACT_TYPE.upper()}.

{context}

Generate a complete, well-structured {self.ARTIFACT_TYPE.upper()} based on the above information.

You have access to the following tools: {', '.join(self.tool_names)}
Use these tools as needed to gather information before generating the artifact."""

    def validate_inputs(self, state: PWIAgentState) -> tuple[bool, str | None]:
        """Validate that all required inputs are present.

        Args:
            state: Current state to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        required = self.get_required_inputs()
        missing = [r for r in required if r not in state.artifacts]

        if missing:
            return False, f"Missing required artifacts: {', '.join(missing)}"
        return True, None

    def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool and return the result.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.

        Returns:
            Tool execution result.
        """
        try:
            result = self._registry.execute(tool_name, **arguments)
            logger.info(f"Tool {tool_name} executed successfully")
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return {"success": False, "error": str(e)}

    def _parse_tool_calls(self, response: Any) -> list[dict[str, Any]]:
        """Parse tool calls from LLM response.

        Args:
            response: LLM completion response.

        Returns:
            List of tool call dictionaries.
        """
        tool_calls = []

        # Handle different response formats
        if hasattr(response, "tool_calls") and response.tool_calls:
            for call in response.tool_calls:
                tool_calls.append({
                    "id": getattr(call, "id", None),
                    "name": call.function.name,
                    "arguments": json.loads(call.function.arguments),
                })
        elif hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and hasattr(choice.message, "tool_calls"):
                if choice.message.tool_calls:
                    for call in choice.message.tool_calls:
                        tool_calls.append({
                            "id": getattr(call, "id", None),
                            "name": call.function.name,
                            "arguments": json.loads(call.function.arguments),
                        })

        return tool_calls

    def _extract_content(self, response: Any) -> str | None:
        """Extract content from LLM response.

        Args:
            response: LLM completion response.

        Returns:
            Content string or None.
        """
        if hasattr(response, "content"):
            return response.content
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and hasattr(choice.message, "content"):
                return choice.message.content
        return None

    async def step(self, state: PWIAgentState) -> PWIAgentState:
        """Execute one step of the agent.

        This is the core method that implements the OpenHands Agent pattern.
        It processes the current state, makes an LLM call (potentially with
        tool use), and returns the updated state.

        Args:
            state: Current agent state.

        Returns:
            Updated state after this step.
        """
        if not self.llm:
            state.error = "LLM client not configured"
            state.is_complete = True
            return state

        # Validate inputs on first step
        if state.current_step == 0:
            is_valid, error = self.validate_inputs(state)
            if not is_valid:
                state.error = error
                state.is_complete = True
                return state

        # Check step limit
        if state.current_step >= state.max_steps:
            state.error = "Maximum steps exceeded"
            state.is_complete = True
            return state

        # Build messages
        messages = self._build_messages(state)

        try:
            # Make LLM completion call with tools
            response = await self.llm.acomplete_with_tools(
                messages=messages,
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                tools=self.tools if self.tools else None,
            )

            # Parse tool calls
            tool_calls = self._parse_tool_calls(response)

            if tool_calls:
                # Check if we've hit the tool call limit
                if len(state.called_tools) >= state.max_unique_tool_calls:
                    logger.info(f"Reached max tool calls ({state.max_unique_tool_calls}) - forcing artifact generation")
                    state.messages.append({
                        "role": "user",
                        "content": "You have made enough tool calls. "
                        "Please generate the artifact NOW based on the data you have collected. "
                        "Do not make any more tool calls.",
                    })
                    state.current_step += 1
                    return state

                # Filter out duplicate tool calls
                new_tool_calls = []
                for call in tool_calls:
                    # Create a unique key for this tool call
                    call_key = f"{call['name']}:{json.dumps(call['arguments'], sort_keys=True)}"
                    if call_key not in state.called_tools:
                        state.called_tools.append(call_key)
                        new_tool_calls.append(call)
                    else:
                        logger.warning(f"Skipping duplicate tool call: {call['name']}")

                # If all tool calls were duplicates, force artifact generation
                if not new_tool_calls:
                    logger.info("All tool calls were duplicates - forcing artifact generation")
                    # Add a message to force the model to generate the artifact
                    state.messages.append({
                        "role": "user",
                        "content": "You have already retrieved all the necessary information. "
                        "Please generate the artifact NOW based on the data you have collected. "
                        "Do not make any more tool calls.",
                    })
                    state.current_step += 1
                    return state

                # Execute only new tool calls
                for call in new_tool_calls:
                    result = self.execute_tool(call["name"], call["arguments"])
                    state.tool_outputs.append({
                        "tool": call["name"],
                        "arguments": call["arguments"],
                        "result": result,
                    })

                    # Format tool call for OpenAI API - must include 'type' and 'function'
                    formatted_tool_call = {
                        "id": call.get("id", f"call_{call['name']}"),
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": json.dumps(call["arguments"]),
                        },
                    }

                    # Add assistant message with tool call
                    state.messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [formatted_tool_call],
                    })
                    # Add tool result message
                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": formatted_tool_call["id"],
                        "content": json.dumps(result),
                    })

                state.current_step += 1
                return state

            # No tool calls - extract final content
            content = self._extract_content(response)
            if content:
                # Process and clean the content
                artifact_content = self._process_response(content)
                state.artifacts[self.ARTIFACT_TYPE] = artifact_content
                state.is_complete = True

                logger.info(f"Agent {self.AGENT_NAME} completed successfully")
            else:
                state.error = "No content in LLM response"
                state.is_complete = True

        except Exception as e:
            logger.error(f"Agent {self.AGENT_NAME} step failed: {e}")
            state.error = str(e)
            state.is_complete = True

        state.current_step += 1
        return state

    def _process_response(self, content: str) -> str:
        """Process the LLM response content.

        Subclasses can override this to extract specific parts or
        transform the content.

        Args:
            content: Raw response content from the LLM.

        Returns:
            Processed artifact content.
        """
        # Remove markdown code fences if present
        content = content.strip()
        if content.startswith("```markdown"):
            content = content[11:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()

    async def run(self, state: PWIAgentState) -> PWIAgentResult:
        """Run the agent to completion.

        This method repeatedly calls step() until the agent completes
        or encounters an error.

        Args:
            state: Initial agent state.

        Returns:
            PWIAgentResult with the execution outcome.
        """
        logger.info(f"Starting agent {self.AGENT_NAME} for session {state.session_id}")

        while not state.is_complete:
            state = await self.step(state)

        if state.error:
            return PWIAgentResult.failure_result(state.error)

        artifact_content = state.artifacts.get(self.ARTIFACT_TYPE)
        if not artifact_content:
            return PWIAgentResult.failure_result("No artifact generated")

        return PWIAgentResult.success_result(
            artifact_type=self.ARTIFACT_TYPE,
            artifact_content=artifact_content,
            artifact_format=self.ARTIFACT_FORMAT,
            model=self.config.model,
            tool_calls=[
                {"tool": o["tool"], "arguments": o["arguments"]}
                for o in state.tool_outputs
            ],
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.AGENT_NAME}, model={self.config.model})"
