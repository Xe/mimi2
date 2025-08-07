"""
Database module for persisting conversations, threads, and tickets.
Provides SQLite storage for all conversation data, metadata, and analytics.
"""

import aiosqlite
import json
import uuid6
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import os


@dataclass
class Ticket:
    """Represents a support ticket."""
    ticket_id: str
    customer_name: str
    customer_email: str
    status: str  # open, waiting, escalated, closed
    created_at: datetime
    updated_at: datetime
    discord_thread_id: Optional[str] = None
    summary: Optional[str] = None
    escalation_reason: Optional[str] = None


@dataclass
class Message:
    """Represents a message in a conversation."""
    message_id: str
    ticket_id: str
    role: str  # user, assistant, system, tool
    content: str
    metadata: Dict[str, Any]
    created_at: datetime
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ToolUsage:
    """Represents tool usage by the agent."""
    usage_id: str
    ticket_id: str
    message_id: Optional[str]
    tool_name: str
    tool_args: Dict[str, Any]
    tool_result: Any
    created_at: datetime
    execution_time_ms: Optional[float] = None


class ConversationDB:
    """Database manager for conversation persistence."""
    
    def __init__(self, db_path: str = "./var/conversations.db"):
        """Initialize the database connection."""
        self.db_path = db_path
        # Ensure the directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    async def initialize(self):
        """Initialize the database schema."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    customer_name TEXT NOT NULL,
                    customer_email TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    discord_thread_id TEXT,
                    summary TEXT,
                    escalation_reason TEXT
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT, -- JSON
                    created_at TIMESTAMP NOT NULL,
                    tool_calls TEXT, -- JSON array
                    tool_call_id TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tool_usage (
                    usage_id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL,
                    message_id TEXT,
                    tool_name TEXT NOT NULL,
                    tool_args TEXT NOT NULL, -- JSON
                    tool_result TEXT NOT NULL, -- JSON
                    execution_time_ms REAL,
                    created_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id),
                    FOREIGN KEY (message_id) REFERENCES messages (message_id)
                )
            """)
            
            # Create indexes for better query performance
            await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_ticket_id ON messages (ticket_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages (created_at)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_tool_usage_ticket_id ON tool_usage (ticket_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets (status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_tickets_discord_thread ON tickets (discord_thread_id)")
            
            await db.commit()
    
    async def create_ticket(self, ticket_id: str, customer_name: str, customer_email: str, 
                          discord_thread_id: Optional[str] = None, summary: Optional[str] = None) -> Ticket:
        """Create a new ticket."""
        now = datetime.now(timezone.utc)
        ticket = Ticket(
            ticket_id=ticket_id,
            customer_name=customer_name,
            customer_email=customer_email,
            status="open",
            created_at=now,
            updated_at=now,
            discord_thread_id=discord_thread_id,
            summary=summary
        )
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO tickets (ticket_id, customer_name, customer_email, status, 
                                   created_at, updated_at, discord_thread_id, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket.ticket_id, ticket.customer_name, ticket.customer_email,
                ticket.status, ticket.created_at.isoformat(), ticket.updated_at.isoformat(),
                ticket.discord_thread_id, ticket.summary
            ))
            await db.commit()
        
        return ticket
    
    async def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Get a ticket by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Ticket(
                        ticket_id=row["ticket_id"],
                        customer_name=row["customer_name"],
                        customer_email=row["customer_email"],
                        status=row["status"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                        discord_thread_id=row["discord_thread_id"],
                        summary=row["summary"],
                        escalation_reason=row["escalation_reason"]
                    )
        return None
    
    async def get_ticket_by_discord_thread(self, discord_thread_id: str) -> Optional[Ticket]:
        """Get a ticket by Discord thread ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM tickets WHERE discord_thread_id = ?", (discord_thread_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return Ticket(
                        ticket_id=row["ticket_id"],
                        customer_name=row["customer_name"],
                        customer_email=row["customer_email"],
                        status=row["status"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                        discord_thread_id=row["discord_thread_id"],
                        summary=row["summary"],
                        escalation_reason=row["escalation_reason"]
                    )
        return None
    
    async def update_ticket_status(self, ticket_id: str, status: str, escalation_reason: Optional[str] = None):
        """Update ticket status."""
        now = datetime.now(timezone.utc)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE tickets 
                SET status = ?, updated_at = ?, escalation_reason = ?
                WHERE ticket_id = ?
            """, (status, now.isoformat(), escalation_reason, ticket_id))
            await db.commit()
    
    async def update_ticket_discord_thread(self, ticket_id: str, discord_thread_id: str):
        """Update the Discord thread ID for a ticket."""
        now = datetime.now(timezone.utc)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE tickets 
                SET discord_thread_id = ?, updated_at = ?
                WHERE ticket_id = ?
            """, (discord_thread_id, now.isoformat(), ticket_id))
            await db.commit()
    
    async def add_message(self, ticket_id: str, role: str, content: str, 
                         metadata: Optional[Dict[str, Any]] = None,
                         tool_calls: Optional[List[Dict]] = None,
                         tool_call_id: Optional[str] = None) -> Message:
        """Add a message to a conversation."""
        message_id = str(uuid6.uuid7())
        now = datetime.now(timezone.utc)
        
        message = Message(
            message_id=message_id,
            ticket_id=ticket_id,
            role=role,
            content=content,
            metadata=metadata or {},
            created_at=now,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id
        )
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO messages (message_id, ticket_id, role, content, metadata, 
                                    created_at, tool_calls, tool_call_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.message_id, message.ticket_id, message.role, message.content,
                json.dumps(message.metadata), message.created_at.isoformat(),
                json.dumps(message.tool_calls) if message.tool_calls else None,
                message.tool_call_id
            ))
            await db.commit()
        
        # Update ticket updated_at timestamp
        await self._update_ticket_timestamp(ticket_id)
        
        return message
    
    async def get_conversation_messages(self, ticket_id: str, limit: Optional[int] = None) -> List[Message]:
        """Get all messages for a conversation, ordered by creation time."""
        query = "SELECT * FROM messages WHERE ticket_id = ? ORDER BY created_at"
        params: List[Any] = [ticket_id]
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                messages = []
                for row in rows:
                    metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                    tool_calls = json.loads(row["tool_calls"]) if row["tool_calls"] else None
                    
                    messages.append(Message(
                        message_id=row["message_id"],
                        ticket_id=row["ticket_id"],
                        role=row["role"],
                        content=row["content"],
                        metadata=metadata,
                        created_at=datetime.fromisoformat(row["created_at"]),
                        tool_calls=tool_calls,
                        tool_call_id=row["tool_call_id"]
                    ))
                return messages
    
    async def record_tool_usage(self, ticket_id: str, message_id: Optional[str], 
                              tool_name: str, tool_args: Dict[str, Any], 
                              tool_result: Any, execution_time_ms: Optional[float] = None) -> ToolUsage:
        """Record tool usage."""
        usage_id = str(uuid6.uuid7())
        now = datetime.now(timezone.utc)
        
        tool_usage = ToolUsage(
            usage_id=usage_id,
            ticket_id=ticket_id,
            message_id=message_id,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=tool_result,
            created_at=now,
            execution_time_ms=execution_time_ms
        )
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO tool_usage (usage_id, ticket_id, message_id, tool_name, 
                                      tool_args, tool_result, execution_time_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tool_usage.usage_id, tool_usage.ticket_id, tool_usage.message_id,
                tool_usage.tool_name, json.dumps(tool_usage.tool_args),
                json.dumps(tool_usage.tool_result), tool_usage.execution_time_ms,
                tool_usage.created_at.isoformat()
            ))
            await db.commit()
        
        return tool_usage
    
    async def get_tool_usage_for_ticket(self, ticket_id: str) -> List[ToolUsage]:
        """Get all tool usage for a ticket."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM tool_usage WHERE ticket_id = ? ORDER BY created_at
            """, (ticket_id,)) as cursor:
                rows = await cursor.fetchall()
                usage_records = []
                for row in rows:
                    usage_records.append(ToolUsage(
                        usage_id=row["usage_id"],
                        ticket_id=row["ticket_id"],
                        message_id=row["message_id"],
                        tool_name=row["tool_name"],
                        tool_args=json.loads(row["tool_args"]),
                        tool_result=json.loads(row["tool_result"]),
                        created_at=datetime.fromisoformat(row["created_at"]),
                        execution_time_ms=row["execution_time_ms"]
                    ))
                return usage_records
    
    async def get_tickets_by_status(self, status: str, limit: Optional[int] = None) -> List[Ticket]:
        """Get tickets by status."""
        query = "SELECT * FROM tickets WHERE status = ? ORDER BY updated_at DESC"
        params: List[Any] = [status]
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                tickets = []
                for row in rows:
                    tickets.append(Ticket(
                        ticket_id=row["ticket_id"],
                        customer_name=row["customer_name"],
                        customer_email=row["customer_email"],
                        status=row["status"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                        discord_thread_id=row["discord_thread_id"],
                        summary=row["summary"],
                        escalation_reason=row["escalation_reason"]
                    ))
                return tickets
    
    async def get_conversation_summary(self, ticket_id: str) -> Dict[str, Any]:
        """Get a summary of a conversation including message counts, tool usage, etc."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Get ticket info
            ticket = await self.get_ticket(ticket_id)
            if not ticket:
                return {}
            
            # Get message counts by role
            async with db.execute("""
                SELECT role, COUNT(*) as count FROM messages 
                WHERE ticket_id = ? GROUP BY role
            """, (ticket_id,)) as cursor:
                message_counts = {row["role"]: row["count"] for row in await cursor.fetchall()}
            
            # Get tool usage counts
            async with db.execute("""
                SELECT tool_name, COUNT(*) as count FROM tool_usage 
                WHERE ticket_id = ? GROUP BY tool_name
            """, (ticket_id,)) as cursor:
                tool_counts = {row["tool_name"]: row["count"] for row in await cursor.fetchall()}
            
            # Get first and last message times
            async with db.execute("""
                SELECT MIN(created_at) as first_message, MAX(created_at) as last_message
                FROM messages WHERE ticket_id = ?
            """, (ticket_id,)) as cursor:
                row = await cursor.fetchone()
                first_message = row["first_message"] if row else None
                last_message = row["last_message"] if row else None
            
            return {
                "ticket": ticket,
                "message_counts": message_counts,
                "tool_usage_counts": tool_counts,
                "first_message_at": first_message,
                "last_message_at": last_message,
                "total_messages": sum(message_counts.values())
            }
    
    async def search_conversations(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search conversations by content."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT DISTINCT m.ticket_id, t.customer_name, t.customer_email, 
                       t.status, t.summary, m.content, m.created_at
                FROM messages m
                JOIN tickets t ON m.ticket_id = t.ticket_id
                WHERE m.content LIKE ? OR t.summary LIKE ?
                ORDER BY m.created_at DESC
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit)) as cursor:
                rows = await cursor.fetchall()
                results = []
                for row in rows:
                    results.append({
                        "ticket_id": row["ticket_id"],
                        "customer_name": row["customer_name"],
                        "customer_email": row["customer_email"],
                        "status": row["status"],
                        "summary": row["summary"],
                        "matching_content": row["content"][:200] + "..." if len(row["content"]) > 200 else row["content"],
                        "message_date": row["created_at"]
                    })
                return results
    
    async def _update_ticket_timestamp(self, ticket_id: str):
        """Update the ticket's updated_at timestamp."""
        now = datetime.now(timezone.utc)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE tickets SET updated_at = ? WHERE ticket_id = ?
            """, (now.isoformat(), ticket_id))
            await db.commit()
    
    async def recreate_conversation_for_agent(self, ticket_id: str) -> List[Dict[str, Any]]:
        """Recreate conversation messages in OpenAI format for agent context restoration."""
        messages = await self.get_conversation_messages(ticket_id)
        openai_messages = []
        
        for msg in messages:
            message_dict: Dict[str, Any] = {
                "role": msg.role,
                "content": msg.content
            }
            
            # Add tool calls if present
            if msg.tool_calls:
                message_dict["tool_calls"] = msg.tool_calls
            
            # Add tool call ID if this is a tool response
            if msg.tool_call_id:
                message_dict["tool_call_id"] = msg.tool_call_id
                message_dict["name"] = msg.metadata.get("tool_name", "unknown")
            
            openai_messages.append(message_dict)
        
        return openai_messages


# Global database instance for main application
db = ConversationDB()

# Function to create database instances for specific use cases
def get_discord_db() -> ConversationDB:
    """Get database instance for Discord bot."""
    return ConversationDB("./var/discord_conversations.db")

def get_test_db() -> ConversationDB:
    """Get database instance for tests."""
    return ConversationDB("./var/test_conversations.db")
