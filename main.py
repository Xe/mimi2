import json
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure Ollama endpoint and model from environment variables
client = OpenAI(
    base_url=os.getenv("OLLAMA_URL", "http://localhost:11434") + "/v1",
    api_key=os.getenv("OPENAI_API_KEY", "ollama"),  # Use OpenAI key or fallback to ollama
)

# Load system prompt from external file
def load_system_prompt():
    """Load the system prompt from system_prompt.txt"""
    try:
        with open("system_prompt.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        # Fallback prompt if file is missing
        return "You are Mimi Yasomi, an AI customer support agent for Techaro's Anubis product."

SYSTEM_PROMPT = load_system_prompt()

# --- Tool implementations (placeholders) ---

def lookup_info(email_address):
    # TODO: integrate with customer database
    return {"id": "cust_12345", "name": "Example User", "email": email_address}


def lookup_logs(customer_id, regex):
    # TODO: query logs store
    return ["2025-08-01 INFO: ...", "2025-08-02 ERROR: ..."]


def lookup_knowledgebase(issue_keyword):
    # TODO: search knowledge base and issue tracker
    return ["KB Article 1 summary...", "Issue #42 details..."]


def note(text):
    # TODO: write internal note
    print(f"[NOTE] {text}")


def reply(body):
    print(f"Reply:\n{body}")
    # Returns the email body to send
    return body


def escalate(issue_summary):
    # TODO: escalate to human
    print(f"[ESCALATE] {issue_summary}")
    return "Issue escalated to human support."


def close(reason):
    # TODO: close ticket in backend
    print(f"[CLOSE] {reason}")
    return f"Ticket closed: {reason}"


def python(code):
    # Execute arbitrary Python (use with caution)
    local_vars = {}
    exec(code, {}, local_vars)
    return local_vars


def wait_for_reply(note):
    print(f"Waiting for reply: {note}")
    pass

# --- Tool schema definitions for the new tools API ---
TOOL_DEFINITIONS = [
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "lookup_info",
    #         "description": "Retrieve customer account details by email.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {"email_address": {"type": "string"}},
    #             "required": ["email_address"]
    #         }
    #     }
    # },
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "lookup_logs",
    #         "description": "Fetch logs for a customer by regex.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "customer_id": {"type": "string"},
    #                 "regex": {"type": "string"}
    #             },
    #             "required": ["customer_id", "regex"]
    #         }
    #     }
    # },
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "lookup_knowledgebase",
    #         "description": "Search KB and issue tracker for issue information.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {"issue_keyword": {"type": "string"}},
    #             "required": ["issue_keyword"]
    #         }
    #     }
    # },
    {
        "type": "function",
        "function": {
            "name": "note",
            "description": "Leave an internal note.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for_reply",
            "description": "Leave an internal note.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reply",
            "description": "Send a user-facing email reply.",
            "parameters": {
                "type": "object",
                "properties": {"body": {"type": "string"}},
                "required": ["body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "escalate",
            "description": "Forward the issue to human support.",
            "parameters": {
                "type": "object",
                "properties": {"issue_summary": {"type": "string"}},
                "required": ["issue_summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close",
            "description": "Close the ticket.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "python",
            "description": "Execute Python code for diagnostics.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"]
            }
        }
    }
]

# --- Agent Loop using modern OpenAI client ---

def invoke_agent(customer_email, user_message):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Customer Email: {customer_email}\nMessage: {user_message}"}
    ]

    while True:
        # Use the new interface for chat completions with tools
        response = client.chat.completions.create(
            model=os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
            messages=messages,  # type: ignore
            tools=TOOL_DEFINITIONS,  # type: ignore
            tool_choice="auto"
        )
        msg = response.choices[0].message

        print(msg.model_dump_json())

        if msg.tool_calls:
            # Process tool calls
            # Convert message to dict for adding to messages list
            msg_dict = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(msg_dict)  # type: ignore
            
            for tool_call in msg.tool_calls:
                if tool_call.function.name == "wait_for_reply":
                    return "Waiting for reply"

                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                result = globals()[fn_name](**fn_args)
                messages.append({  # type: ignore
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": fn_name,
                    "content": json.dumps(result)
                })
            continue

        return msg.content

# Example usage
def main():
    customer_email = input("Customer email: ")
    user_message = input("Customer message: ")
    response = invoke_agent(customer_email, user_message)
    print("\n--- Agent Response ---\n")
    print(response)

if __name__ == "__main__":
    main()
