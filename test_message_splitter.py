"""
Tests for message splitting utility.
"""

import unittest
from message_splitter import split_message


class TestMessageSplitter(unittest.TestCase):
    
    def test_short_message_unchanged(self):
        """Test that short messages are returned as-is."""
        message = "This is a short message."
        result = split_message(message)
        self.assertEqual(result, [message])
    
    def test_empty_message(self):
        """Test that empty messages are handled properly."""
        result = split_message("")
        self.assertEqual(result, [""])
    
    def test_message_at_limit(self):
        """Test that messages at exactly the limit are not split."""
        message = "x" * 2000
        result = split_message(message)
        self.assertEqual(result, [message])
    
    def test_message_over_limit_no_code_blocks(self):
        """Test splitting of long messages without code blocks."""
        # Create a message that's definitely over the limit
        message = "This is a long message. " * 100  # ~2400 characters
        result = split_message(message)
        
        # Should be split into multiple parts
        self.assertGreater(len(result), 1)
        
        # Each part should be under the limit
        for part in result:
            self.assertLessEqual(len(part), 2000)
        
        # When rejoined, should contain the same content (minus extra spaces)
        rejoined = " ".join(result)
        self.assertIn("This is a long message.", rejoined)
    
    def test_single_code_block_in_own_message(self):
        """Test that code blocks are isolated in their own messages."""
        message = """Here's some code:
        
```python
def hello():
    print("Hello, world!")
```

And some text after."""
        
        result = split_message(message)
        
        # Should have at least 2 parts
        self.assertGreaterEqual(len(result), 2)
        
        # One part should contain only the code block
        code_block_found = False
        for part in result:
            if part.strip().startswith('```python') and part.strip().endswith('```'):
                code_block_found = True
                self.assertIn('def hello():', part)
                self.assertIn('print("Hello, world!")', part)
        
        self.assertTrue(code_block_found, "Code block should be in its own message")
    
    def test_multiple_code_blocks(self):
        """Test handling of multiple code blocks."""
        message = """First block:
        
```python
print("first")
```

Some text in between.

```javascript
console.log("second");
```

Final text."""
        
        result = split_message(message)
        
        # Should have multiple parts
        self.assertGreater(len(result), 2)
        
        # Count code blocks in results
        code_blocks = 0
        for part in result:
            if '```' in part:
                code_blocks += 1
        
        self.assertGreaterEqual(code_blocks, 2, "Should preserve both code blocks")
    
    def test_very_large_code_block(self):
        """Test splitting of code blocks that exceed the message limit."""
        # Create a large code block
        large_code = "print('line')\n" * 200  # ~2600 characters
        message = f"```python\n{large_code}```"
        
        result = split_message(message)
        
        # Should be split into multiple parts
        self.assertGreater(len(result), 1)
        
        # Each part should be under the limit
        for part in result:
            self.assertLessEqual(len(part), 2000)
        
        # All parts should maintain code block structure
        for part in result:
            self.assertTrue(part.startswith('```python'))
            self.assertTrue(part.endswith('```'))
    
    def test_mixed_content_long_message(self):
        """Test a long message with mixed content including code blocks."""
        message = """This is a very long explanation about programming. """ * 20 + """

Here's an example:

```python
def complex_function():
    # This is a complex function
    for i in range(100):
        print(f"Processing item {i}")
        if i % 10 == 0:
            print("Checkpoint reached")
    return "Done"
```

And here's more explanation. """ * 30 + """

```javascript
function anotherExample() {
    console.log("Another example");
    return true;
}
```

Final thoughts. """ * 10
        
        result = split_message(message)
        
        # Should be split into multiple parts
        self.assertGreater(len(result), 3)
        
        # Each part should be under the limit
        for part in result:
            self.assertLessEqual(len(part), 2000)
        
        # Should preserve code blocks
        python_found = False
        javascript_found = False
        for part in result:
            if '```python' in part:
                python_found = True
            if '```javascript' in part:
                javascript_found = True
        
        self.assertTrue(python_found, "Python code block should be preserved")
        self.assertTrue(javascript_found, "JavaScript code block should be preserved")
    
    def test_code_block_only_message(self):
        """Test a message that is only a code block."""
        message = """```python
def hello():
    print("Hello, world!")
    return True
```"""
        
        result = split_message(message)
        
        # Should be a single message since it's not too long
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], message)
    
    def test_custom_max_length(self):
        """Test using a custom maximum length."""
        message = "This is a test message that is longer than 50 characters for sure."
        result = split_message(message, max_length=50)
        
        # Should be split
        self.assertGreater(len(result), 1)
        
        # Each part should be under the custom limit
        for part in result:
            self.assertLessEqual(len(part), 50)
    
    def test_word_boundary_splitting(self):
        """Test that messages are split at word boundaries when possible."""
        message = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10"
        result = split_message(message, max_length=30)
        
        # Should be split
        self.assertGreater(len(result), 1)
        
        # Parts should not break words (no partial words)
        for part in result:
            words = part.strip().split()
            for word in words:
                self.assertNotIn(' ', word.strip())  # No spaces within words


if __name__ == "__main__":
    unittest.main()