"""
Provider-agnostic LLM client with tool-calling agent loop.
Uses litellm to seamlessly proxy any provider (OpenAI, Anthropic, Gemini, etc).
"""
import os
import json
import inspect
import asyncio
from typing import Callable
from litellm import acompletion

# --- Provider base URL mapping ---
PROVIDER_DEFAULTS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}

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

def get_litellm_kwargs(api_key: str, provider: str = "gemini", base_url: str = None) -> dict:
    """Get the correct litellm arguments depending on provider."""
    # Litellm model string needs provider/ prefix for some providers
    # The agent expects OpenAI API structure. Litellm handles the translation natively.
    kwargs = {
        "api_key": api_key,
    }
    
    if base_url:
        kwargs["api_base"] = base_url.strip().rstrip('/')
    
    return kwargs

async def run_agent_loop(
    client=None, # kept for signature compatibility but unused
    model: str = "gpt-4o",
    system_prompt: str = "",
    user_prompt: str = "",
    tools: list[Callable] = None,
    max_iterations: int = 30,
    log_callback=None,
    provider: str = "gemini",
    base_url: str = None,
    api_key: str = None
) -> str:
    """
    Run a tool-calling agent loop using litellm.
    """
    if tools is None:
        tools = []
        
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
    
    litellm_kwargs = get_litellm_kwargs(api_key, provider, base_url)
    
    # Prefix model with provider if needed for litellm
    if provider == "anthropic" and not model.startswith("anthropic/"):
        model_name = f"anthropic/{model}"
    elif provider == "gemini" and not model.startswith("gemini/"):
        model_name = f"gemini/{model}"
    else:
        model_name = model
    
    for iteration in range(max_iterations):
        try:
            response = await acompletion(
                model=model_name,
                messages=messages,
                tools=tool_schemas if tool_schemas else None,
                tool_choice="auto" if tool_schemas else None,
                **litellm_kwargs
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
