# Mimi2 - AI Customer Support Agent

This is an AI-powered customer support agent for Techaro and Anubis, featuring function calling capabilities with modern OpenAI client integration.

## Features

- Modern OpenAI client with tool calling support
- Customer information lookup
- Log analysis and troubleshooting
- Knowledge base integration
- Escalation and ticket management
- Python code execution for diagnostics

## Requirements

- Python 3.12+
- OpenAI-compatible API endpoint (configured for Ollama)
- uv package manager

## Installation

```bash
uv sync
```

## Usage

Run the application:

```bash
uv run python main.py
```

## Configuration

The application uses environment variables for configuration and an external system prompt file.

### Environment Variables
Copy the `.env` file and modify as needed:

```bash
cp .env.example .env  # if using a template, or edit .env directly
```

Environment variables:
- `OLLAMA_URL` - Ollama server URL (default: http://localhost:11434)
- `OLLAMA_MODEL` - Model to use (default: gpt-oss:20b)
- `OPENAI_API_KEY` - API key for authentication (default: ollama)

### System Prompt
The AI agent's behavior is defined in `system_prompt.txt`. Edit this file to customize:
- Agent personality and tone
- Available tools and their descriptions
- Workflow instructions
- Company-specific guidelines

Make sure you have:
1. Ollama running at the configured URL
2. The specified model available in Ollama
3. `system_prompt.txt` in the project root

## Available Tools

- `lookup_info(email_address)` - Retrieve customer account details
- `lookup_logs(customer_id, regex)` - Fetch customer logs
- `lookup_knowledgebase(issue_keyword)` - Search knowledge base
- `note(text)` - Leave internal notes
- `reply(body)` - Send email replies
- `escalate(issue_summary)` - Escalate to human support
- `close(reason)` - Close tickets
- `python(code)` - Execute Python diagnostics