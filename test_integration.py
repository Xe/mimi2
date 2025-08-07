"""
Integration test demonstrating Discord message splitting functionality.
This simulates scenarios that would occur in the Discord bot.
"""

import sys
from message_splitter import split_message


def test_real_world_scenarios():
    """Test realistic scenarios that might occur in Discord bot responses."""
    
    print("=== Discord Message Splitting Integration Test ===\n")
    
    try:
        # Scenario 1: Agent response with code example
        print("1. Agent response with code example:")
        response1 = """I can help you with that Python error. Here's how to fix it:

The issue is in your function definition. Here's the corrected code:

```python
def calculate_average(numbers):
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)

# Example usage:
numbers = [1, 2, 3, 4, 5]
result = calculate_average(numbers)
print(f"Average: {result}")
```

This should resolve the ZeroDivisionError you were experiencing. The key change is adding a check for empty lists before performing the division."""
        
        parts1 = split_message(response1)
        print(f"Split into {len(parts1)} parts:")
        for i, part in enumerate(parts1, 1):
            print(f"  Part {i} ({len(part)} chars): {part[:50]}...")
        print()
        
        # Scenario 2: Very long technical explanation
        print("2. Long technical explanation:")
        response2 = """This is a complex issue that requires a detailed explanation. """ * 25 + """

The root cause is related to memory management and garbage collection in Python. Here are the key points:

1. Memory allocation patterns
2. Reference counting mechanisms  
3. Garbage collection cycles
4. Memory fragmentation issues

""" + """Here's additional technical detail that continues for a while. """ * 30 + """

Let me know if you need more clarification on any of these points!"""
        
        parts2 = split_message(response2)
        print(f"Split into {len(parts2)} parts:")
        for i, part in enumerate(parts2, 1):
            print(f"  Part {i} ({len(part)} chars): {part[:50]}...")
        print()
        
        # Scenario 3: Multiple code blocks in one response
        print("3. Multiple code blocks:")
        response3 = """Here are two different approaches to solve your problem:

**Approach 1: Using a simple loop**

```python
def method_one(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
    return result
```

**Approach 2: Using list comprehension**

```python
def method_two(data):
    return [item * 2 for item in data if item > 0]
```

Both methods will give you the same result, but the second one is more Pythonic and concise."""
        
        parts3 = split_message(response3)
        print(f"Split into {len(parts3)} parts:")
        for i, part in enumerate(parts3, 1):
            print(f"  Part {i} ({len(part)} chars): {part[:50]}...")
            if "```" in part:
                print(f"    → Contains code block")
        print()
        
        # Scenario 4: Very large code block
        print("4. Large code block that exceeds limit:")
        large_code = "\n".join([f"    line_{i} = process_data_{i}(input_data)" for i in range(50)])
        response4 = f"""Here's the complete implementation:

```python
def large_function(input_data):
{large_code}
    return final_result
```

This function handles all the data processing steps."""
        
        parts4 = split_message(response4)
        print(f"Split into {len(parts4)} parts:")
        for i, part in enumerate(parts4, 1):
            print(f"  Part {i} ({len(part)} chars): {'Code block' if part.startswith('```') else part[:50]}...")
        print()
        
        # Scenario 5: Message at exactly the limit
        print("5. Message at Discord limit (2000 chars):")
        response5 = "This message is exactly at the limit. " + "X" * (2000 - 38)
        parts5 = split_message(response5)
        print(f"Original length: {len(response5)}")
        print(f"Split into {len(parts5)} parts")
        print()
        
        print("=== All tests completed successfully! ===")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_real_world_scenarios()
    sys.exit(0 if success else 1)