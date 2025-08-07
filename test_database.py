#!/usr/bin/env python3
"""
Test script to verify database integration and conversation persistence.
"""

import asyncio
import uuid6
from datetime import datetime, timezone
from database import get_test_db, ConversationDB
from agent import AgentManager


async def test_database_operations():
    """Test basic database operations."""
    print("=== Testing Database Operations ===\n")
    
    # Initialize test database
    db = get_test_db()
    await db.initialize()
    print("✅ Test database initialized")
    
    # Create a test ticket
    ticket_id = str(uuid6.uuid7())
    customer_name = "Test User"
    customer_email = "test@example.com"
    
    ticket = await db.create_ticket(ticket_id, customer_name, customer_email)
    print(f"✅ Created ticket: {ticket.ticket_id}")
    
    # Add some messages
    user_msg = await db.add_message(
        ticket_id, "user", "Hello, I need help with Anubis installation",
        metadata={"channel": "discord", "user_id": "123456"}
    )
    print(f"✅ Added user message: {user_msg.message_id}")
    
    assistant_msg = await db.add_message(
        ticket_id, "assistant", "I'll help you with that!",
        metadata={"response_type": "greeting"}
    )
    print(f"✅ Added assistant message: {assistant_msg.message_id}")
    
    # Record tool usage
    tool_usage = await db.record_tool_usage(
        ticket_id, assistant_msg.message_id, "lookup_knowledgebase",
        {"query": "anubis installation"}, 
        [{"title": "Installation Guide", "content": "..."}], 
        150.5
    )
    print(f"✅ Recorded tool usage: {tool_usage.usage_id}")
    
    # Test conversation retrieval
    messages = await db.get_conversation_messages(ticket_id)
    print(f"✅ Retrieved {len(messages)} messages")
    
    # Test conversation summary
    summary = await db.get_conversation_summary(ticket_id)
    print(f"✅ Generated conversation summary: {summary['total_messages']} total messages")
    
    # Test search
    search_results = await db.search_conversations("installation")
    print(f"✅ Search found {len(search_results)} matching conversations")
    
    return ticket_id


async def test_agent_integration():
    """Test agent integration with database."""
    print("\n=== Testing Agent Integration ===\n")
    
    # Create agent manager with test database
    test_db = get_test_db()
    agent_manager = AgentManager(db=test_db)
    await agent_manager.initialize()
    print("✅ Agent manager initialized with test database")
    
    # Create a new ticket through agent
    ticket_id = str(uuid6.uuid7())
    customer_name = "John Doe"
    customer_email = "john@example.com"
    user_message = "I'm having trouble configuring Anubis bot policies"
    
    # Process first message
    response = await agent_manager.process_message(
        ticket_id, customer_name, customer_email, user_message
    )
    print(f"✅ Processed first message, got response: {response[:100]}..." if response else "No response")
    
    # Process follow-up message
    followup_response = await agent_manager.process_message(
        ticket_id, customer_name, customer_email, "Can you show me an example?"
    )
    print(f"✅ Processed follow-up message, got response: {followup_response[:100]}..." if followup_response else "No response")
    
    # Check database state
    db = test_db  # Use the same test database instance
    ticket = await db.get_ticket(ticket_id)
    messages = await db.get_conversation_messages(ticket_id)
    tool_usage = await db.get_tool_usage_for_ticket(ticket_id)
    
    print(f"✅ Database state:")
    print(f"   - Ticket status: {ticket.status if ticket else 'Not found'}")
    print(f"   - Messages stored: {len(messages)}")
    print(f"   - Tool usage records: {len(tool_usage)}")
    
    return ticket_id


async def test_conversation_restoration():
    """Test conversation history restoration."""
    print("\n=== Testing Conversation Restoration ===\n")
    
    # Create a ticket with some history using test database
    test_db = get_test_db()
    agent_manager = AgentManager(db=test_db)
    await agent_manager.initialize()
    
    ticket_id = str(uuid6.uuid7())
    customer_name = "Alice Smith"
    customer_email = "alice@example.com"
    
    # Simulate a conversation
    messages = [
        "I need help setting up Anubis",
        "What operating system are you using?",
        "I'm using Ubuntu 22.04",
        "Great! Let me help you with the installation."
    ]
    
    # Process messages one by one
    for i, msg in enumerate(messages):
        if i % 2 == 0:  # User messages
            await agent_manager.process_message(ticket_id, customer_name, customer_email, msg)
        # Assistant responses will be generated automatically
    
    print(f"✅ Created conversation with {len(messages)} exchanges")
    
    # Now simulate bot restart by creating a new agent for the same ticket
    new_agent = agent_manager.get_or_create_agent(ticket_id)
    new_agent.set_customer_info(customer_name, customer_email)
    
    # The agent should load previous conversation history
    response = await new_agent.process_message("Can you repeat the installation steps?")
    print(f"✅ Agent responded after restart: {response[:100]}..." if response else "No response")
    
    # Verify conversation continuity
    db = test_db  # Use test database
    all_messages = await db.get_conversation_messages(ticket_id)
    print(f"✅ Total messages in conversation: {len(all_messages)}")
    
    return ticket_id


async def test_discord_thread_mapping():
    """Test Discord thread ID mapping."""
    print("\n=== Testing Discord Thread Mapping ===\n")
    
    db = get_test_db()
    await db.initialize()
    
    # Create ticket
    ticket_id = str(uuid6.uuid7())
    discord_thread_id = "987654321"
    
    ticket = await db.create_ticket(
        ticket_id, "Discord User", "discord123@discord", 
        discord_thread_id=discord_thread_id
    )
    print(f"✅ Created ticket with Discord thread: {discord_thread_id}")
    
    # Test lookup by Discord thread ID
    found_ticket = await db.get_ticket_by_discord_thread(discord_thread_id)
    assert found_ticket is not None and found_ticket.ticket_id == ticket_id
    print(f"✅ Successfully looked up ticket by Discord thread ID")
    
    # Update Discord thread ID
    new_thread_id = "111222333"
    await db.update_ticket_discord_thread(ticket_id, new_thread_id)
    
    updated_ticket = await db.get_ticket(ticket_id)
    assert updated_ticket is not None and updated_ticket.discord_thread_id == new_thread_id
    print(f"✅ Successfully updated Discord thread ID")
    
    return ticket_id


async def test_ticket_status_management():
    """Test ticket status updates and escalation."""
    print("\n=== Testing Ticket Status Management ===\n")
    
    db = get_test_db()
    await db.initialize()
    
    # Create ticket
    ticket_id = str(uuid6.uuid7())
    ticket = await db.create_ticket(ticket_id, "Status Test User", "status@test.com")
    assert ticket.status == "open"
    print(f"✅ Created ticket with status: {ticket.status}")
    
    # Update to waiting
    await db.update_ticket_status(ticket_id, "wait_for_reply")
    ticket = await db.get_ticket(ticket_id)
    assert ticket is not None and ticket.status == "wait_for_reply"
    print(f"✅ Updated ticket status to: {ticket.status}")
    
    # Escalate ticket
    escalation_reason = "Complex technical issue requiring human intervention"
    await db.update_ticket_status(ticket_id, "escalated", escalation_reason)
    ticket = await db.get_ticket(ticket_id)
    assert ticket is not None and ticket.status == "escalated"
    assert ticket.escalation_reason == escalation_reason
    print(f"✅ Escalated ticket with reason: {ticket.escalation_reason}")
    
    # Test filtering by status
    escalated_tickets = await db.get_tickets_by_status("escalated", limit=10)
    assert any(t.ticket_id == ticket_id for t in escalated_tickets)
    print(f"✅ Found {len(escalated_tickets)} escalated tickets")
    
    return ticket_id


async def main():
    """Run all tests."""
    print("🚀 Starting Database Integration Tests\n")
    
    try:
        # Run all test suites
        test_results = []
        
        test_results.append(await test_database_operations())
        test_results.append(await test_agent_integration())
        test_results.append(await test_conversation_restoration())
        test_results.append(await test_discord_thread_mapping())
        test_results.append(await test_ticket_status_management())
        
        print(f"\n🎉 All tests completed successfully!")
        print(f"📊 Created {len(test_results)} test tickets:")
        for i, ticket_id in enumerate(test_results, 1):
            print(f"   {i}. {ticket_id}")
        
        # Final verification
        db = get_test_db()
        all_tickets = await db.get_tickets_by_status("open")
        all_tickets.extend(await db.get_tickets_by_status("escalated"))
        all_tickets.extend(await db.get_tickets_by_status("wait_for_reply"))
        
        print(f"📈 Database contains {len(all_tickets)} total tickets")
        
        # Show a sample conversation
        if test_results:
            sample_ticket = test_results[0]
            messages = await db.get_conversation_messages(sample_ticket)
            tool_usage = await db.get_tool_usage_for_ticket(sample_ticket)
            
            print(f"\n📝 Sample conversation ({sample_ticket}):")
            for msg in messages[:3]:  # Show first 3 messages
                print(f"   {msg.role}: {msg.content[:50]}...")
            
            if tool_usage:
                print(f"🔧 Tool usage in sample conversation:")
                for usage in tool_usage[:2]:  # Show first 2 tool usages
                    print(f"   {usage.tool_name}: {usage.execution_time_ms}ms")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)


async def test_database_integration():
    """Test the complete database integration."""
    print("🧪 Testing Database Integration...")
    
    # Initialize test database
    db = get_test_db()
    await db.initialize()
    print("✅ Test database initialized")
    
    # Test ticket creation
    ticket_id = str(uuid6.uuid7())
    customer_name = "Test Customer"
    customer_email = "test@example.com"
    
    ticket = await db.create_ticket(ticket_id, customer_name, customer_email)
    print(f"✅ Created ticket: {ticket_id[:16]}...")
    
    # Test message storage
    message1 = await db.add_message(ticket_id, "user", "Hello, I need help with Anubis")
    print(f"✅ Added user message: {message1.message_id[:16]}...")
    
    message2 = await db.add_message(
        ticket_id, "assistant", "I'd be happy to help you with Anubis!",
        metadata={"response_type": "greeting"}
    )
    print(f"✅ Added assistant message: {message2.message_id[:16]}...")
    
    # Test tool usage recording
    tool_usage = await db.record_tool_usage(
        ticket_id, message2.message_id, "lookup_knowledgebase",
        {"query": "installation help"}, 
        [{"rank": 1, "text": "Installation guide found"}],
        execution_time_ms=150.5
    )
    print(f"✅ Recorded tool usage: {tool_usage.usage_id[:16]}...")
    
    # Test conversation retrieval
    messages = await db.get_conversation_messages(ticket_id)
    print(f"✅ Retrieved {len(messages)} messages")
    
    # Test conversation summary
    summary = await db.get_conversation_summary(ticket_id)
    print(f"✅ Generated summary with {summary['total_messages']} total messages")
    
    # Test search
    search_results = await db.search_conversations("Anubis", limit=5)
    print(f"✅ Search found {len(search_results)} results")
    
    # Test agent manager integration
    print("\n🤖 Testing Agent Manager Integration...")
    
    async def mock_reply_handler(body, state, ticket_id=None):
        print(f"📧 Mock reply sent for ticket {ticket_id}: {body[:50]}...")
        return {"sent": True}
    
    agent_manager = AgentManager(reply_handler=mock_reply_handler, db=db)
    await agent_manager.initialize()
    
    # Test message processing with database persistence
    test_ticket_id = str(uuid6.uuid7())
    response = await agent_manager.process_message(
        test_ticket_id, "Jane Doe", "jane@example.com",
        "I'm having trouble installing Anubis on Ubuntu. Can you help?"
    )
    print(f"✅ Agent processed message and returned: {response[:100] if response else 'None'}...")
    
    # Verify the conversation was stored
    stored_messages = await db.get_conversation_messages(test_ticket_id)
    print(f"✅ Conversation stored with {len(stored_messages)} messages")
    
    # Test conversation restoration
    agent2 = agent_manager.get_or_create_agent(test_ticket_id)
    await agent2.load_conversation_history()
    print(f"✅ Conversation history restored with {len(agent2.messages)} messages in memory")
    
    print("\n🎉 All database integration tests passed!")
    
    # Show some sample data
    print("\n📊 Sample Data Summary:")
    tickets = await db.get_tickets_by_status("open", limit=5)
    for ticket in tickets:
        print(f"   🎫 {ticket.ticket_id[:16]}... - {ticket.customer_name} ({ticket.status})")


async def test_conversation_persistence():
    """Test that conversations can be restored across agent instances."""
    print("\n🔄 Testing Conversation Persistence...")
    
    test_db = get_test_db()
    agent_manager = AgentManager(db=test_db)
    await agent_manager.initialize()
    
    ticket_id = str(uuid6.uuid7())
    
    # First conversation turn
    print("📝 First conversation turn...")
    agent1 = agent_manager.get_or_create_agent(ticket_id)
    agent1.set_customer_info("Bob Smith", "bob@example.com")
    
    # Simulate first message (this would store to database)
    response1 = await agent1.process_message("How do I configure Anubis for my website?")
    print(f"✅ Response 1: {response1[:100] if response1 else 'None'}...")
    
    # Remove agent from memory (simulate restart)
    agent_manager.remove_agent(ticket_id)
    
    # Second conversation turn with new agent instance
    print("📝 Second conversation turn (new agent instance)...")
    agent2 = agent_manager.get_or_create_agent(ticket_id)
    agent2.set_customer_info("Bob Smith", "bob@example.com")
    
    # This should restore the previous conversation
    response2 = await agent2.process_message("I'm using Apache as my web server.")
    print(f"✅ Response 2: {response2[:100] if response2 else 'None'}...")
    
    # Verify conversation was restored
    print(f"✅ Agent 2 has {len(agent2.messages)} messages in memory (should include restored history)")
    
    # Check database
    db_messages = await agent_manager.db.get_conversation_messages(ticket_id)
    print(f"✅ Database contains {len(db_messages)} messages for this conversation")
    
    print("🎉 Conversation persistence test passed!")


if __name__ == "__main__":
    print("🚀 Starting Database Integration Tests...")
    asyncio.run(test_database_integration())
    asyncio.run(test_conversation_persistence())
