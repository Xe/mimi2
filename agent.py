import json
import os
import asyncio
import time
from typing import Dict, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

from docs.search import search as docs_search
from database import db, ConversationDB


class AgentManager:
    """
    Manages multiple agent instances, one per ticket.
    """
    
    def __init__(self, reply_handler=None, escalation_handler=None, db=None):
        self.agents: Dict[str, Agent] = {}
        self.reply_handler = reply_handler
        self.escalation_handler = escalation_handler
        self.db = db if db is not None else globals()["db"]
    
    async def initialize(self):
        """Initialize the database."""
        await self.db.initialize()
    
    def get_or_create_agent(self, ticket_id: str) -> "Agent":
        """
        Gets an existing agent for a ticket or creates a new one.
        """
        if ticket_id not in self.agents:
            self.agents[ticket_id] = Agent(
                ticket_id=ticket_id,
                reply_handler=self.reply_handler,
                escalation_handler=self.escalation_handler,
                db=self.db
            )
        return self.agents[ticket_id]
    
    def remove_agent(self, ticket_id: str) -> None:
        """
        Removes an agent when a ticket is closed.
        """
        if ticket_id in self.agents:
            del self.agents[ticket_id]
    
    async def process_message(self, ticket_id: str, customer_name: str, customer_email: str, user_message: str) -> Optional[str]:
        """
        Processes a message for a specific ticket.
        """
        agent = self.get_or_create_agent(ticket_id)
        
        # Set customer info if this is the first time we're seeing this ticket
        if agent.customer_info is None:
            agent.set_customer_info(customer_name, customer_email)
            # Create ticket in database if it doesn't exist
            existing_ticket = await self.db.get_ticket(ticket_id)
            if not existing_ticket:
                await self.db.create_ticket(ticket_id, customer_name, customer_email)
        
        return await agent.process_message(user_message)


class Agent:
    """
    An AI agent that maintains conversation state for a specific ticket.
    """

    def __init__(self, ticket_id, reply_handler=None, escalation_handler=None, db=None):
        """
        Initializes the Agent for a specific ticket.
        """
        load_dotenv()
        self.client = AsyncOpenAI(
            base_url=os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "ollama"),
        )
        self.system_prompt = self._load_system_prompt()
        self.tool_definitions = self._get_tool_definitions()
        self.reply_handler = reply_handler
        self.escalation_handler = escalation_handler
        self.ticket_id = ticket_id
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.customer_info = None
        self.db = db or ConversationDB()
        self.current_message_id = None  # Track current message for tool usage

    def _load_system_prompt(self):
        """
        Loads the system prompt from the system_prompt.md file.
        """
        try:
            with open("system_prompt.md", "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return "You are Mimi Yasomi, an AI customer support agent for Techaro's Anubis product."

    def _get_tool_definitions(self):
        """
        Returns the schema definitions for the tools available to the agent.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "lookup_knowledgebase",
                    "description": "Search docs site, knowledge base, and issue tracker for issue information.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "note",
                    "description": "Leave an internal note.",
                    "parameters": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "reply",
                    "description": "Send a user-facing email reply.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "body": {"type": "string"},
                            "state": {
                                "type": "string",
                                "enum": [
                                    "closed",
                                    "wait_for_reply",
                                ],
                            },
                        },
                        "required": ["body", "state"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "escalate",
                    "description": "Escalate the issue to human support when the agent cannot resolve it.",
                    "parameters": {
                        "type": "object",
                        "properties": {"issue_summary": {"type": "string"}},
                        "required": ["issue_summary"],
                    },
                },
            },
        ]

    # --- Tool Implementations ---

    def lookup_knowledgebase(self, query):
        """
        Searches the knowledge base for a given query.
        """
        print(f"[DOCS] {query}")
        start_time = time.time()
        
        try:
            df = docs_search(query, limit=10)
            if df is None or len(df) == 0:
                result = []
            else:
                results = []
                for i, row in enumerate(df.itertuples(index=False), start=1):
                    file_path = str(getattr(row, "file_path", ""))
                    section = int(getattr(row, "section", 0))
                    text_val = getattr(row, "text", "")
                    text_str = text_val.decode("utf-8", errors="ignore") if isinstance(text_val, (bytes, bytearray)) else str(text_val)
                    
                    result_dict = {
                        "rank": i,
                        "file_path": file_path,
                        "section": section,
                        "reference": f"{file_path}#section-{section}",
                        "text": text_str
                    }
                    results.append(result_dict)
                result = results
            
            # Record tool usage
            execution_time = (time.time() - start_time) * 1000
            asyncio.create_task(self.db.record_tool_usage(
                self.ticket_id, self.current_message_id, "lookup_knowledgebase",
                {"query": query}, result, execution_time
            ))
            
            return result
        except Exception as e:
            print(f"[ERROR] Knowledge base search failed: {e}")
            # Record failed tool usage
            execution_time = (time.time() - start_time) * 1000
            asyncio.create_task(self.db.record_tool_usage(
                self.ticket_id, self.current_message_id, "lookup_knowledgebase",
                {"query": query}, {"error": str(e)}, execution_time
            ))
            return []

    def note(self, text):
        """
        Creates an internal note.
        """
        print(f"[NOTE] {text}")
        # Record tool usage
        asyncio.create_task(self.db.record_tool_usage(
            self.ticket_id, self.current_message_id, "note",
            {"text": text}, {"noted": True}, None
        ))
        return {"noted": True}

    async def reply(self, body="", state="open", **kwargs):
        """
        Sends a reply to the user.
        """
        start_time = time.time()
        
        # Update ticket status in database
        await self.db.update_ticket_status(self.ticket_id, state)
        
        result = None
        if self.reply_handler is not None:
            if asyncio.iscoroutinefunction(self.reply_handler):
                result = await self.reply_handler(body=body, state=state, ticket_id=self.ticket_id)
            else:
                result = self.reply_handler(body=body, state=state, ticket_id=self.ticket_id)
        else:
            print(f"\nTicket {self.ticket_id} - State: {state}\nReply:\n{body}")
            result = body
        
        # Record tool usage
        execution_time = (time.time() - start_time) * 1000
        await self.db.record_tool_usage(
            self.ticket_id, self.current_message_id, "reply",
            {"body": body, "state": state}, result, execution_time
        )
        
        return result

    async def escalate(self, issue_summary):
        """
        Escalates an issue to human support.
        """
        start_time = time.time()
        
        # Update ticket status in database
        await self.db.update_ticket_status(self.ticket_id, "escalated", issue_summary)
        
        result = None
        if self.escalation_handler is not None:
            if asyncio.iscoroutinefunction(self.escalation_handler):
                result = await self.escalation_handler(issue_summary=issue_summary, ticket_id=self.ticket_id)
            else:
                result = self.escalation_handler(issue_summary=issue_summary, ticket_id=self.ticket_id)
        else:
            print(f"[ESCALATE] Ticket {self.ticket_id}: {issue_summary}")
            result = "Issue escalated to human support."
        
        # Record tool usage
        execution_time = (time.time() - start_time) * 1000
        await self.db.record_tool_usage(
            self.ticket_id, self.current_message_id, "escalate",
            {"issue_summary": issue_summary}, result, execution_time
        )
        
        return result

    def close(self, reason):
        """
        Closes the support ticket.
        """
        print(f"[CLOSE] {reason}")
        # Record tool usage
        asyncio.create_task(self.db.record_tool_usage(
            self.ticket_id, self.current_message_id, "close",
            {"reason": reason}, {"closed": True}, None
        ))
        # Update ticket status
        asyncio.create_task(self.db.update_ticket_status(self.ticket_id, "closed"))
        return f"Ticket closed: {reason}"

    def python(self, code):
        """
        Executes Python code.
        """
        start_time = time.time()
        try:
            local_vars = {}
            exec(code, {}, local_vars)
            result = local_vars
        except Exception as e:
            result = {"error": str(e)}
        
        # Record tool usage
        execution_time = (time.time() - start_time) * 1000
        asyncio.create_task(self.db.record_tool_usage(
            self.ticket_id, self.current_message_id, "python",
            {"code": code}, result, execution_time
        ))
        return result

    def wait_for_reply(self, note):
        """
        Waits for a reply from the user.
        """
        print(f"Waiting for reply: {note}")

    def set_customer_info(self, customer_name, customer_email):
        """
        Sets the customer information for this ticket.
        """
        self.customer_info = {
            "name": customer_name,
            "email": customer_email
        }

    async def load_conversation_history(self):
        """
        Load existing conversation history from database and restore agent state.
        """
        try:
            # Get existing messages and restore conversation state
            stored_messages = await self.db.recreate_conversation_for_agent(self.ticket_id)
            if stored_messages:
                # Keep only the system message and append stored messages
                self.messages = [self.messages[0]] + stored_messages
                print(f"[DB] Restored {len(stored_messages)} messages for ticket {self.ticket_id}")
        except Exception as e:
            print(f"[DB] Failed to load conversation history: {e}")

    async def process_message(self, user_message):
        """
        Processes a new message from the user and returns the agent's response.
        This method accumulates conversation history and can be called multiple times.
        """
        # Load existing conversation history if this is the first message processing
        if len(self.messages) == 1:  # Only system message
            await self.load_conversation_history()
        
        # Store the user message in database
        if self.customer_info:
            formatted_message = f"Customer: {self.customer_info['name']} ({self.customer_info['email']})\nMessage: {user_message}"
        else:
            formatted_message = user_message
        
        user_msg = await self.db.add_message(
            self.ticket_id, "user", formatted_message,
            metadata={"original_content": user_message, "customer_info": self.customer_info}
        )
            
        self.messages.append({"role": "user", "content": formatted_message})

        while True:
            response = await self.client.chat.completions.create(
                model=os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
                messages=self.messages,  # type: ignore
                tools=self.tool_definitions,  # type: ignore
                tool_choice="auto",
            )
            msg = response.choices[0].message
            msg_dict = msg.to_dict()

            if "reasoning" in msg_dict:
                print(f"[REASONING] Ticket {self.ticket_id}: {msg_dict['reasoning']}")

            if msg.tool_calls:
                # Store assistant message with tool calls
                assistant_msg = await self.db.add_message(
                    self.ticket_id, "assistant", msg.content or "",
                    tool_calls=[{
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    } for tc in msg.tool_calls]
                )
                self.current_message_id = assistant_msg.message_id
                
                # Add the assistant's message with tool calls to history
                msg_dict = {"role": "assistant", "content": msg.content}
                if msg.tool_calls:
                    msg_dict["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                self.messages.append(msg_dict)

                sent_reply = False

                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)
                    
                    # Check if the method is async and await it if necessary
                    method = getattr(self, fn_name)
                    if asyncio.iscoroutinefunction(method):
                        result = await method(**fn_args)
                    else:
                        result = method(**fn_args)
                    
                    # Store tool result message
                    await self.db.add_message(
                        self.ticket_id, "tool", json.dumps(result),
                        metadata={"tool_name": fn_name, "tool_args": fn_args},
                        tool_call_id=tool_call.id
                    )
                    
                    # Add the tool result to conversation history
                    self.messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": fn_name,
                            "content": json.dumps(result),
                        }
                    )

                    if tool_call.function.name == "reply":
                        sent_reply = True

                if sent_reply:
                    # Add the final assistant response to history
                    if msg.content:
                        await self.db.add_message(
                            self.ticket_id, "assistant", msg.content,
                            metadata={"final_response": True}
                        )
                        self.messages.append({"role": "assistant", "content": msg.content})
                    return msg.content or ""
                continue
            else:
                # No tool calls, add the response to history and return
                content = msg.content or ""
                if content:
                    await self.db.add_message(
                        self.ticket_id, "assistant", content,
                        metadata={"direct_response": True}
                    )
                    self.messages.append({"role": "assistant", "content": content})
                return content

    async def invoke(self, ticket_id, customer_name, customer_email, user_message):
        """
        Legacy method for backwards compatibility. 
        For new code, use set_customer_info() and process_message() instead.
        """
        if self.ticket_id != ticket_id:
            raise ValueError(f"Agent is for ticket {self.ticket_id}, not {ticket_id}")
        
        self.set_customer_info(customer_name, customer_email)
        return await self.process_message(user_message)
