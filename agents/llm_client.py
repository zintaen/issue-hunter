"""
Provider-agnostic LLM client with tool-calling agent loop.
Uses the OpenAI SDK as a universal client since most providers
(OpenAI, Anthropic proxies, Gemini, custom endpoints) support the
OpenAI-compatible chat completions API.
"""
import os
import json
import inspect
import asyncio
from typing import Callable
from openai import AsyncOpenAI

# --- Provider base URL mapping ---
PROVIDER_DEFAULTS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}

DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
    "gemini": "gemini-2.5-flash",
}


def get_client(api_key: str, provider: str = "gemini", base_url: str = None) -> AsyncOpenAI:
    """Create an AsyncOpenAI client configured for any provider."""
    effective_base_url = base_url or PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])
    return AsyncOpenAI(api_key=api_key, base_url=effective_base_url)


def _python_type_to_json_schema(annotation) -> dict:
    """Convert Python type annotations to JSON Schema types."""
    if annotation == str or annotation == inspect.Parameter.empty:
        return {"type": "string"}
    elif annotation == int:
        return {"type": "integer"}
    elif annotation == float:
        return {"type": "number"}
    elif annotation == bool:
        return {"type": "boolean"}
    else:
        return {"type": "string"}


def function_to_tool_schema(func: Callable) -> dict:
    """Convert a Python function into an OpenAI-compatible tool schema."""
    sig = inspect.signature(func)
    doc = inspect.getdoc(func) or ""
    
    properties = {}
    required = []
    
    for name, param in sig.parameters.items():
        prop = _python_type_to_json_schema(param.annotation)
        # Use the first line of the docstring as description if available
        prop["description"] = f"Parameter: {name}"
        properties[name] = prop
        if param.default == inspect.Parameter.empty:
            required.append(name)
    
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": doc,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            }
        }
    }


async def run_agent_loop(
    client: AsyncOpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    tools: list[Callable],
    max_iterations: int = 30,
    log_callback=None,
) -> str:
    """
    Run a tool-calling agent loop.
    
    Sends the user prompt to the LLM with tool schemas. When the LLM
    returns tool_calls, executes them and feeds results back. Repeats
    until the LLM returns a final text response (no tool calls).
    """
    async def log(msg: str):
        if log_callback:
            if asyncio.iscoroutinefunction(log_callback):
                await log_callback(msg)
            else:
                log_callback(msg)

    # Build tool registry and schemas
    tool_map = {func.__name__: func for func in tools}
    tool_schemas = [function_to_tool_schema(func) for func in tools]
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    
    for iteration in range(max_iterations):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tool_schemas if tool_schemas else None,
                tool_choice="auto" if tool_schemas else None,
            )
        except Exception as e:
            error_msg = f"LLM API call failed: {e}"
            await log(error_msg)
            return error_msg
        
        choice = response.choices[0]
        message = choice.message
        
        # Append the assistant message to conversation
        messages.append(message.model_dump())
        
        # If no tool calls, we have the final response
        if not message.tool_calls:
            return message.content or ""
        
        # Execute each tool call
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}
            
            await log(f"  🔧 {func_name}({', '.join(f'{k}={repr(v)[:60]}' for k, v in args.items())})")
            
            func = tool_map.get(func_name)
            if not func:
                result = f"Error: Unknown tool '{func_name}'"
            else:
                try:
                    result = func(**args)
                    # Handle async functions
                    if asyncio.iscoroutine(result):
                        result = await result
                    result = str(result) if result is not None else "Done."
                except Exception as e:
                    result = f"Error executing {func_name}: {e}"
            
            # Truncate very long results to avoid context overflow
            if len(result) > 15000:
                result = result[:15000] + "\n... (truncated)"
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })
    
    return "Agent reached maximum iterations without completing."
