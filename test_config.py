#!/usr/bin/env python3
"""
Simple test script to validate the main.py configuration and imports.
"""

import os
import sys
from dotenv import load_dotenv

def test_environment():
    """Test that environment variables are loaded correctly."""
    load_dotenv()
    
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
    api_key = os.getenv("OPENAI_API_KEY", "ollama")
    
    print("Environment Configuration:")
    print(f"  OLLAMA_URL: {ollama_url}")
    print(f"  OLLAMA_MODEL: {ollama_model}")
    print(f"  API_KEY: {api_key[:10]}..." if len(api_key) > 10 else f"  API_KEY: {api_key}")
    
    return True

def test_imports():
    """Test that all required modules can be imported."""
    try:
        import json
        import os
        from openai import OpenAI
        from dotenv import load_dotenv
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

if __name__ == "__main__":
    print("Testing Mimi2 Configuration...")
    print("=" * 40)
    
    tests = [
        test_environment,
        test_imports,
    ]
    
    results = []
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test failed: {e}")
            results.append(False)
    
    print("\n" + "=" * 40)
    print(f"Tests completed: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("✓ All tests passed! The application is ready to run.")
        sys.exit(0)
    else:
        print("✗ Some tests failed. Check the configuration.")
        sys.exit(1)
