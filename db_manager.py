#!/usr/bin/env python3
"""
Database management utility for viewing conversations and tickets.
"""

import asyncio
import argparse
import json
from datetime import datetime
from typing import Optional

from database import ConversationDB, get_discord_db


async def list_tickets(db: ConversationDB, status: Optional[str] = None, limit: int = 10):
    """List tickets with optional status filter."""
    if status:
        tickets = await db.get_tickets_by_status(status, limit)
        print(f"\n📋 Tickets with status '{status}' (limit: {limit}):")
    else:
        # Get all statuses
        all_tickets = []
        for status_filter in ["open", "waiting", "escalated", "closed"]:
            tickets = await db.get_tickets_by_status(status_filter, limit)
            all_tickets.extend(tickets)
        tickets = sorted(all_tickets, key=lambda t: t.updated_at, reverse=True)[:limit]
        print(f"\n📋 All tickets (limit: {limit}):")
    
    if not tickets:
        print("No tickets found.")
        return
    
    for ticket in tickets:
        print(f"\n🎫 {ticket.ticket_id[:16]}...")
        print(f"   👤 {ticket.customer_name} ({ticket.customer_email})")
        print(f"   📅 Created: {ticket.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   📅 Updated: {ticket.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   📊 Status: {ticket.status}")
        if ticket.summary:
            print(f"   📝 Summary: {ticket.summary}")
        if ticket.discord_thread_id:
            print(f"   💬 Discord Thread: {ticket.discord_thread_id}")


async def show_conversation(db: ConversationDB, ticket_id: str):
    """Show full conversation for a ticket."""
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        print(f"❌ Ticket {ticket_id} not found.")
        return
    
    messages = await db.get_conversation_messages(ticket_id)
    summary = await db.get_conversation_summary(ticket_id)
    
    print(f"\n💬 Conversation for Ticket {ticket_id[:16]}...")
    print(f"👤 Customer: {ticket.customer_name} ({ticket.customer_email})")
    print(f"📊 Status: {ticket.status}")
    print(f"📅 Created: {ticket.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📈 Total Messages: {summary.get('total_messages', 0)}")
    
    if messages:
        print("\n📝 Messages:")
        for i, msg in enumerate(messages, 1):
            timestamp = msg.created_at.strftime('%H:%M:%S')
            role_emoji = {
                "user": "👤",
                "assistant": "🤖", 
                "system": "⚙️",
                "tool": "🔧"
            }.get(msg.role, "❓")
            
            print(f"\n[{i:2d}] {role_emoji} {msg.role.upper()} ({timestamp})")
            if msg.tool_call_id:
                print(f"     🔗 Tool Call ID: {msg.tool_call_id}")
            
            # Truncate long messages
            content = msg.content
            if len(content) > 200:
                content = content[:200] + "..."
            print(f"     {content}")
            
            if msg.tool_calls:
                print(f"     🔧 Tool Calls: {len(msg.tool_calls)}")


async def show_tool_usage(db: ConversationDB, ticket_id: str):
    """Show tool usage for a ticket."""
    ticket = await db.get_ticket(ticket_id)
    if not ticket:
        print(f"❌ Ticket {ticket_id} not found.")
        return
    
    tool_usage = await db.get_tool_usage_for_ticket(ticket_id)
    
    print(f"\n🔧 Tool Usage for Ticket {ticket_id[:16]}...")
    print(f"📊 Total Tool Calls: {len(tool_usage)}")
    
    if tool_usage:
        tool_counts = {}
        for usage in tool_usage:
            tool_counts[usage.tool_name] = tool_counts.get(usage.tool_name, 0) + 1
        
        print("\n📈 Tool Usage Summary:")
        for tool_name, count in tool_counts.items():
            print(f"   🔧 {tool_name}: {count} calls")
        
        print("\n📝 Detailed Tool Usage:")
        for i, usage in enumerate(tool_usage, 1):
            timestamp = usage.created_at.strftime('%H:%M:%S')
            exec_time = f" ({usage.execution_time_ms:.1f}ms)" if usage.execution_time_ms else ""
            print(f"\n[{i:2d}] 🔧 {usage.tool_name}{exec_time} ({timestamp})")
            print(f"     📥 Args: {json.dumps(usage.tool_args, indent=6)}")
            
            # Truncate long results
            result_str = json.dumps(usage.tool_result, indent=6)
            if len(result_str) > 300:
                result_str = result_str[:300] + "..."
            print(f"     📤 Result: {result_str}")


async def search_conversations(db: ConversationDB, query: str, limit: int = 5):
    """Search conversations by content."""
    results = await db.search_conversations(query, limit)
    
    print(f"\n🔍 Search results for '{query}' (limit: {limit}):")
    
    if not results:
        print("No results found.")
        return
    
    for i, result in enumerate(results, 1):
        print(f"\n[{i}] 🎫 Ticket {result['ticket_id'][:16]}...")
        print(f"    👤 {result['customer_name']} ({result['customer_email']})")
        print(f"    📊 Status: {result['status']}")
        if result['summary']:
            print(f"    📝 Summary: {result['summary']}")
        print(f"    💬 Matching content: {result['matching_content']}")
        print(f"    📅 Date: {result['message_date']}")


async def get_conversation_summary(db: ConversationDB, ticket_id: str):
    """Get conversation summary with analytics."""
    summary = await db.get_conversation_summary(ticket_id)
    
    if not summary:
        print(f"❌ Ticket {ticket_id} not found.")
        return
    
    ticket = summary["ticket"]
    print(f"\n📊 Summary for Ticket {ticket_id[:16]}...")
    print(f"👤 Customer: {ticket.customer_name} ({ticket.customer_email})")
    print(f"📅 Created: {ticket.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 Updated: {ticket.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Status: {ticket.status}")
    
    if summary["first_message_at"] and summary["last_message_at"]:
        first_msg = datetime.fromisoformat(summary["first_message_at"])
        last_msg = datetime.fromisoformat(summary["last_message_at"])
        duration = last_msg - first_msg
        print(f"⏱️  Duration: {duration}")
    
    print(f"\n📈 Message Statistics:")
    print(f"   📝 Total Messages: {summary['total_messages']}")
    for role, count in summary["message_counts"].items():
        role_emoji = {
            "user": "👤",
            "assistant": "🤖", 
            "system": "⚙️",
            "tool": "🔧"
        }.get(role, "❓")
        print(f"   {role_emoji} {role.title()}: {count}")
    
    if summary["tool_usage_counts"]:
        print(f"\n🔧 Tool Usage:")
        for tool, count in summary["tool_usage_counts"].items():
            print(f"   🔧 {tool}: {count} calls")


async def main():
    parser = argparse.ArgumentParser(description="Database management utility")
    parser.add_argument("command", choices=[
        "list", "show", "tools", "search", "summary"
    ], help="Command to execute")
    parser.add_argument("--ticket-id", help="Ticket ID for show/tools/summary commands")
    parser.add_argument("--status", help="Status filter for list command")
    parser.add_argument("--query", help="Search query for search command")
    parser.add_argument("--limit", type=int, default=10, help="Limit results")
    parser.add_argument("--discord", help="Query Discord conversations?")
    
    args = parser.parse_args()
    
    db = ConversationDB()
    
    if args.discord:
        db = get_discord_db()
    
    await db.initialize()
    
    try:
        if args.command == "list":
            await list_tickets(db, args.status, args.limit)
        elif args.command == "show":
            if not args.ticket_id:
                print("❌ --ticket-id required for show command")
                return
            await show_conversation(db, args.ticket_id)
        elif args.command == "tools":
            if not args.ticket_id:
                print("❌ --ticket-id required for tools command")
                return
            await show_tool_usage(db, args.ticket_id)
        elif args.command == "search":
            if not args.query:
                print("❌ --query required for search command")
                return
            await search_conversations(db, args.query, args.limit)
        elif args.command == "summary":
            if not args.ticket_id:
                print("❌ --ticket-id required for summary command")
                return
            await get_conversation_summary(db, args.ticket_id)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
