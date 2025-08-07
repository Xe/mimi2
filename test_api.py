#!/usr/bin/env python3
"""
Test script to check OpenRouter API connectivity
"""

import os
import sys
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

async def test_api():
    load_dotenv()
    
    client = AsyncOpenAI(
        base_url=os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "ollama"),
    )
    
    model = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
    
    print(f"Testing API with:")
    print(f"  Base URL: {client.base_url}")
    print(f"  Model: {model}")
    print(f"  API Key: {client.api_key[:20]}..." if client.api_key else "No API key")
    print()
    
    success = True
    
    try:
        # Test a simple completion
        print("Testing chat completion...")
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello in exactly 5 words."}
            ],
            max_tokens=50
        )
        
        print("✅ Chat completion successful!")
        print(f"Response: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"❌ Chat completion failed: {e}")
        print(f"Error type: {type(e).__name__}")
        success = False
        
    try:
        # Test with tool calling (which might be causing the 405)
        print("\nTesting tool calling...")
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What's the weather like?"}
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather information",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {"type": "string"}
                            },
                            "required": ["location"]
                        }
                    }
                }
            ],
            tool_choice="auto"
        )
        
        print("✅ Tool calling successful!")
        print(f"Response: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"❌ Tool calling failed: {e}")
        print(f"Error type: {type(e).__name__}")
        success = False
        
        # This might be the source of the 405 error
        if "405" in str(e):
            print("\n🔍 Found 405 error! This is likely the source of the issue.")
            print("The OpenRouter API might not support tool calling for this model.")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(test_api())
    sys.exit(0 if success else 1)
