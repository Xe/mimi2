"""
Message splitting utility for Discord bot to handle messages longer than 2048 characters.
Provides special handling for markdown code blocks.
"""

import re
from typing import List


def split_message(message: str, max_length: int = 2000) -> List[str]:
    """
    Split a message into multiple parts if it exceeds max_length.
    
    Args:
        message: The message to split
        max_length: Maximum length per message (default 2000 to leave buffer for Discord's 2048 limit)
    
    Returns:
        List of message parts, with code blocks isolated in separate messages
    """
    if not message:
        return [""]
    
    # Extract code blocks first
    code_block_pattern = r'```[\s\S]*?```'
    code_blocks = re.findall(code_block_pattern, message)
    
    # If there are code blocks, handle them specially regardless of message length
    if code_blocks:
        return _split_message_with_code_blocks(message, code_blocks, max_length)
    elif len(message) <= max_length:
        return [message]
    else:
        return _split_plain_message(message, max_length)


def _split_message_with_code_blocks(message: str, code_blocks: List[str], max_length: int) -> List[str]:
    """
    Split a message that contains code blocks, ensuring code blocks are in separate messages.
    """
    parts = []
    
    # Split the message by code blocks
    code_block_pattern = r'(```[\s\S]*?```)'
    segments = re.split(code_block_pattern, message)
    
    current_part = ""
    
    for segment in segments:
        if not segment:
            continue
            
        # Check if this segment is a code block
        if segment.startswith('```') and segment.endswith('```'):
            # Flush current part if it exists
            if current_part.strip():
                parts.extend(_split_plain_message(current_part.strip(), max_length))
                current_part = ""
            
            # Add code block as its own message(s)
            if len(segment) <= max_length:
                parts.append(segment)
            else:
                # If code block is too long, split it but preserve the structure
                parts.extend(_split_large_code_block(segment, max_length))
        else:
            # Regular text segment
            if len(current_part + segment) <= max_length:
                current_part += segment
            else:
                # Flush current part and start new one
                if current_part.strip():
                    parts.extend(_split_plain_message(current_part.strip(), max_length))
                current_part = segment
    
    # Add any remaining content
    if current_part.strip():
        parts.extend(_split_plain_message(current_part.strip(), max_length))
    
    return parts


def _split_large_code_block(code_block: str, max_length: int) -> List[str]:
    """
    Split a code block that's too large, preserving the ``` markers.
    """
    # Extract the language identifier and content
    lines = code_block.split('\n')
    first_line = lines[0]  # ```language
    last_line = lines[-1]  # ```
    content_lines = lines[1:-1]  # The actual code content
    
    parts = []
    current_lines = []
    current_length = len(first_line) + len(last_line) + 2  # +2 for newlines
    
    for line in content_lines:
        line_length = len(line) + 1  # +1 for newline
        
        if current_length + line_length > max_length and current_lines:
            # Create a code block with current lines
            code_part = first_line + '\n' + '\n'.join(current_lines) + '\n' + last_line
            parts.append(code_part)
            current_lines = [line]
            current_length = len(first_line) + len(last_line) + line_length + 2
        else:
            current_lines.append(line)
            current_length += line_length
    
    # Add the remaining lines
    if current_lines:
        code_part = first_line + '\n' + '\n'.join(current_lines) + '\n' + last_line
        parts.append(code_part)
    
    return parts


def _split_plain_message(message: str, max_length: int) -> List[str]:
    """
    Split a plain text message without code blocks.
    """
    if len(message) <= max_length:
        return [message]
    
    parts = []
    current_part = ""
    
    # Split by sentences first, then by words if needed
    sentences = re.split(r'(?<=[.!?])\s+', message)
    
    for sentence in sentences:
        if len(current_part + sentence) <= max_length:
            if current_part:
                current_part += " " + sentence
            else:
                current_part = sentence
        else:
            # Flush current part
            if current_part:
                parts.append(current_part)
                current_part = ""
            
            # If sentence is still too long, split by words
            if len(sentence) > max_length:
                parts.extend(_split_by_words(sentence, max_length))
            else:
                current_part = sentence
    
    # Add any remaining content
    if current_part:
        parts.append(current_part)
    
    return parts


def _split_by_words(text: str, max_length: int) -> List[str]:
    """
    Split text by words when sentences are too long.
    """
    parts = []
    words = text.split()
    current_part = ""
    
    for word in words:
        if len(current_part + " " + word) <= max_length:
            if current_part:
                current_part += " " + word
            else:
                current_part = word
        else:
            # Flush current part
            if current_part:
                parts.append(current_part)
                current_part = word
            
            # If single word is still too long, split it (edge case)
            if len(word) > max_length:
                # Split the word itself as last resort
                for i in range(0, len(word), max_length):
                    parts.append(word[i:i + max_length])
                current_part = ""
    
    # Add any remaining content
    if current_part:
        parts.append(current_part)
    
    return parts