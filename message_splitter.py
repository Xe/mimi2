"""
Message splitting utility for Discord bot to handle messages longer than 2000 bytes.
Provides special handling for markdown code blocks.
"""

import re
from typing import List


def split_message(message: str, max_length: int = 1900) -> List[str]:
    """
    Split a message into multiple parts if it exceeds max_length in bytes.
    
    Args:
        message: The message to split
        max_length: Maximum byte length per message (default 1900 to leave buffer for Discord's 2000 byte limit)
    
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
    elif len(message.encode('utf-8')) <= max_length:
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
            if len(segment.encode('utf-8')) <= max_length:
                parts.append(segment)
            else:
                # If code block is too long, split it but preserve the structure
                parts.extend(_split_large_code_block(segment, max_length))
        else:
            # Regular text segment
            if len((current_part + segment).encode('utf-8')) <= max_length:
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
    current_length = len(first_line.encode('utf-8')) + len(last_line.encode('utf-8')) + 2  # +2 for newlines
    
    for line in content_lines:
        line_length = len(line.encode('utf-8')) + 1  # +1 for newline
        
        if current_length + line_length > max_length and current_lines:
            # Create a code block with current lines
            code_part = first_line + '\n' + '\n'.join(current_lines) + '\n' + last_line
            parts.append(code_part)
            current_lines = [line]
            current_length = len(first_line.encode('utf-8')) + len(last_line.encode('utf-8')) + line_length + 2
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
    if len(message.encode('utf-8')) <= max_length:
        return [message]
    
    parts = []
    current_part = ""
    
    # Split by sentences first, then by words if needed
    sentences = re.split(r'(?<=[.!?])\s+', message)
    
    for sentence in sentences:
        test_part = current_part + " " + sentence if current_part else sentence
        if len(test_part.encode('utf-8')) <= max_length:
            current_part = test_part
        else:
            # Flush current part
            if current_part:
                parts.append(current_part)
                current_part = ""
            
            # If sentence is still too long, split by words
            if len(sentence.encode('utf-8')) > max_length:
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
        test_part = current_part + " " + word if current_part else word
        if len(test_part.encode('utf-8')) <= max_length:
            current_part = test_part
        else:
            # Flush current part
            if current_part:
                parts.append(current_part)
                current_part = word
            
            # If single word is still too long, split it (edge case)
            if len(word.encode('utf-8')) > max_length:
                # Split the word itself as last resort
                word_bytes = word.encode('utf-8')
                for i in range(0, len(word_bytes), max_length):
                    chunk = word_bytes[i:i + max_length]
                    # Ensure we don't split in the middle of a multi-byte character
                    try:
                        parts.append(chunk.decode('utf-8'))
                    except UnicodeDecodeError:
                        # Find the last complete character boundary
                        for j in range(len(chunk) - 1, -1, -1):
                            try:
                                parts.append(chunk[:j].decode('utf-8'))
                                # Add the remaining bytes to the next iteration
                                word_bytes = chunk[j:] + word_bytes[i + max_length:]
                                break
                            except UnicodeDecodeError:
                                continue
                current_part = ""
    
    # Add any remaining content
    if current_part:
        parts.append(current_part)
    
    return parts