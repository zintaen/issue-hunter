import asyncio
import os
from litellm import acompletion

async def main():
    api_base = "https://token-plan-sgp.xiaomimimo.com/anthropic"
    api_key = "tp-socv9qlp3ppb6fjvfi7zxy37ebgda3h6zbmel49oabbzpuu7"
    
    # Simple tool
    tool_schemas = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }]
    
    try:
        response = await acompletion(
            model="anthropic/mimo-v2.5",
            messages=[{"role": "user", "content": "Hello"}],
            api_key=api_key,
            api_base=api_base,
            tools=tool_schemas,
            tool_choice="auto"
        )
        print("Success:", response)
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
