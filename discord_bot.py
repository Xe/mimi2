import discord
import os
import uuid6
import asyncio
import re
from typing import cast

from agent import AgentManager
from message_splitter import split_message
from database import get_discord_db

# Initialize Discord-specific database
db = get_discord_db()

async def send_split_message(channel, message: str):
    """
    Send a message that may need to be split into multiple parts due to Discord's 2000 byte limit.
    Code blocks will be isolated in separate messages.
    """
    if not message:
        return
    
    message_parts = split_message(message)
    
    for part in message_parts:
        if part.strip():  # Only send non-empty parts
            await channel.send(part)

def create_reply_handler():
    """Creates a reply handler that sends messages to the current Discord thread"""
    async def reply_handler(body, state, ticket_id=None):
        # Find the thread for this ticket
        if ticket_id:
            ticket = await db.get_ticket(str(ticket_id))
            if ticket and ticket.discord_thread_id:
                # Get the Discord channel object
                try:
                    channel = client.get_channel(int(ticket.discord_thread_id))
                    if isinstance(channel, discord.Thread):
                        await send_split_message(channel, body)
                        if state == "closed":
                            try:
                                await channel.edit(archived=True)
                            except discord.HTTPException:
                                pass  # Thread might already be archived or permission issue
                        return {"sent": True, "ticket_id": ticket_id}
                except (ValueError, discord.NotFound):
                    print(f"Could not find Discord thread {ticket.discord_thread_id} for ticket {ticket_id}")
        return {"sent": False, "ticket_id": ticket_id}
    return reply_handler

def create_escalation_handler():
    """Creates an escalation handler that notifies about escalations in the Discord thread"""
    async def escalation_handler(issue_summary: str, ticket_id=None):
        # Find the thread for this ticket
        if ticket_id:
            ticket = await db.get_ticket(str(ticket_id))
            if ticket and ticket.discord_thread_id:
                # Get the Discord channel object
                try:
                    channel = client.get_channel(int(ticket.discord_thread_id))
                    if isinstance(channel, discord.Thread):
                        # Mark this ticket as escalated in the database
                        await db.update_ticket_status(str(ticket_id), "escalated", issue_summary)
                        
                        escalation_message = f"🚨 **ESCALATED TO HUMAN SUPPORT** 🚨\n\n**Ticket ID:** {ticket_id}\n**Issue Summary:** {issue_summary}\n\nA human support agent will review this ticket and respond as soon as possible.\n\n*Note: This ticket is now managed by human support. The AI will no longer respond to messages in this thread.*"
                        await send_split_message(channel, escalation_message)
                        # Pin the escalation message for visibility
                        try:
                            escalation_msg = await channel.send(f"📌 Ticket {ticket_id} has been escalated and is awaiting human review.")
                            await escalation_msg.pin()
                        except discord.HTTPException:
                            pass  # Could not pin message, continue anyway
                        return {"escalated": True, "summary": issue_summary, "ticket_id": ticket_id}
                except (ValueError, discord.NotFound):
                    print(f"Could not find Discord thread {ticket.discord_thread_id} for ticket {ticket_id}")
        return {"escalated": False, "summary": issue_summary, "ticket_id": ticket_id}
    return escalation_handler # type: ignore

async def generate_thread_summary(agent_manager, content):
    """Generate a concise summary for the thread name using the agent manager's client"""
    try:
        # Create a temporary agent to use its client
        temp_agent = agent_manager.get_or_create_agent("temp_summary")
        response = await temp_agent.client.chat.completions.create(
            model=os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
            messages=[
                {"role": "system", "content": "Create a very brief 1-5 word summary for a support ticket thread name. Be concise and descriptive. No punctuation or special characters except spaces and hyphens."},
                {"role": "user", "content": f"Summarize this support request: {content}"}
            ],
            max_tokens=20,
            temperature=0.3
        )
        # Clean up the temporary agent
        agent_manager.remove_agent("temp_summary")
        
        summary_content = response.choices[0].message.content
        summary = summary_content.strip() if summary_content else "Support Ticket"
        
        # Clean the summary and ensure it's under 50 characters
        clean_summary = re.sub(r'[^\w\s-]', '', summary)[:45]
        return clean_summary if clean_summary else "Support Ticket"
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        # Fallback to simple truncation
        fallback = re.sub(r'[^\w\s-]', '', content[:45]).strip()
        return fallback if fallback else "Support Ticket"

# --- Bot Setup ---
agent_manager = AgentManager(
    reply_handler=create_reply_handler(),
    escalation_handler=create_escalation_handler(),
    db=db  # Use Discord-specific database
)
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    """
    Event handler for when the bot is ready.
    """
    print(f"We have logged in as {client.user}")
    # Initialize the database when the bot starts
    await agent_manager.initialize()
    print("Database initialized successfully")


@client.event
async def on_message(message):
    """
    Event handler for when a message is received.
    """
    print(f"{message.author.id}: {message.content}")
    
    if message.author == client.user:
        return

    # Check if this message is in an existing ticket thread
    if hasattr(message.channel, 'parent') and message.channel.parent:
        # This is a thread message
        thread_id = str(message.channel.id)
        # Look up ticket by Discord thread ID
        ticket = await db.get_ticket_by_discord_thread(thread_id)
        if ticket:
            # This is a follow-up message in an existing ticket
            ticket_id = ticket.ticket_id
            
            # Check if this ticket has been escalated
            if ticket.status == "escalated":
                print(f"Ignoring message in escalated ticket {ticket_id}")
                return
            
            # Use customer info from database
            customer_name = ticket.customer_name
            customer_email = ticket.customer_email
            
            try:
                response = await agent_manager.process_message(
                    ticket_id, 
                    customer_name, 
                    customer_email, 
                    message.content
                )
                
                if response:
                    await send_split_message(message.channel, f"**Response:**\n{response}")
                    
            except Exception as e:
                await message.channel.send(f"❌ **Error processing message:** {str(e)}")
            return

    # Check if the bot is mentioned in the message (new ticket)
    if client.user and client.user in message.mentions:
        # Extract the message content without the bot mention
        content = message.content
        for mention in message.mentions:
            if mention == client.user:
                content = content.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "").strip()
        
        print("got pinged!")
        await message.add_reaction("👀")

        # Use a unique ID for the ticket
        ticket_id = str(uuid6.uuid7())
        
        # Create a new thread for this ticket
        ticket_display = ticket_id[:16].replace("-", "")
        thread = await message.create_thread(
            name=f"🎫 Ticket #{ticket_display}",
            auto_archive_duration=60  # Archive after 1 hour of inactivity
        )

        # Use the Discord user's info
        customer_name = message.author.display_name or message.author.name
        customer_email = f"{message.author.id}@discord"

        # Create the ticket in the database with Discord thread ID
        await db.create_ticket(
            ticket_id=ticket_id,
            customer_name=customer_name,
            customer_email=customer_email,
            discord_thread_id=str(thread.id)
        )

        # Send initial message to thread
        await thread.send(f"**Ticket #{ticket_display}** - Processing your request...")

        # Process the initial message
        try:
            response = await agent_manager.process_message(
                ticket_id, 
                customer_name, 
                customer_email, 
                content
            )
            
            if response:
                await send_split_message(thread, f"**Response:**\n{response}")
                
        except Exception as e:
            await thread.send(f"❌ **Error processing request:** {str(e)}")


def main():
    """
    Main function to run the bot.
    """
    # It is recommended to manage your Discord bot token securely,
    # for example, by using environment variables.
    discord_token = os.getenv("DISCORD_TOKEN")
    if not discord_token:
        raise ValueError("DISCORD_TOKEN environment variable not set.")

    client.run(discord_token)


if __name__ == "__main__":
    main()
