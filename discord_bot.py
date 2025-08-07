import discord
import os
import uuid6
import asyncio
import re

from agent import AgentManager

# Global variables to store the current thread and ticket ID for handlers
current_thread = None
current_ticket_id = None

# Dictionary to track which Discord thread belongs to which ticket
thread_to_ticket = {}
ticket_to_thread = {}
escalated_tickets = set()  # Track escalated tickets to ignore them

def create_reply_handler():
    """Creates a reply handler that sends messages to the current Discord thread"""
    async def reply_handler(body, state, ticket_id=None):
        # Find the thread for this ticket
        thread = ticket_to_thread.get(str(ticket_id)) if ticket_id else current_thread
        if thread:
            await thread.send(body)
            if state == "closed":
                await thread.edit(archived=True)
        return {"sent": True, "ticket_id": ticket_id}
    return reply_handler

def create_escalation_handler():
    """Creates an escalation handler that notifies about escalations in the Discord thread"""
    async def escalation_handler(issue_summary: str, ticket_id=None):
        # Find the thread for this ticket
        thread = ticket_to_thread.get(str(ticket_id)) if ticket_id else current_thread
        if thread:
            # Mark this ticket as escalated
            if ticket_id:
                escalated_tickets.add(str(ticket_id))
            
            escalation_message = f"🚨 **ESCALATED TO HUMAN SUPPORT** 🚨\n\n**Ticket ID:** {ticket_id}\n**Issue Summary:** {issue_summary}\n\nA human support agent will review this ticket and respond as soon as possible.\n\n*Note: This ticket is now managed by human support. The AI will no longer respond to messages in this thread.*"
            await thread.send(escalation_message)
            # Pin the escalation message for visibility
            escalation_msg = await thread.send(f"📌 Ticket {ticket_id} has been escalated and is awaiting human review.")
            await escalation_msg.pin()
        return {"escalated": True, "summary": issue_summary, "ticket_id": ticket_id}
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
    escalation_handler=create_escalation_handler()
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


@client.event
async def on_message(message):
    """
    Event handler for when a message is received.
    """
    global current_thread, current_ticket_id
    
    print(f"{message.author.id}: {message.content}")
    
    if message.author == client.user:
        return

    # Check if this message is in an existing ticket thread
    if hasattr(message.channel, 'parent') and message.channel.parent:
        # This is a thread message
        thread_id = str(message.channel.id)
        if thread_id in thread_to_ticket:
            # This is a follow-up message in an existing ticket
            ticket_id = thread_to_ticket[thread_id]
            
            # Check if this ticket has been escalated
            if ticket_id in escalated_tickets:
                print(f"Ignoring message in escalated ticket {ticket_id}")
                return
            
            current_thread = message.channel
            current_ticket_id = ticket_id
            
            customer_name = message.author.display_name or message.author.name
            customer_email = f"{message.author.id}@discord"
            
            
            try:
                response = await agent_manager.process_message(
                    ticket_id, 
                    customer_name, 
                    customer_email, 
                    message.content
                )
                
                if response:
                    await current_thread.send(f"**Response:**\n{response}")
                    
            except Exception as e:
                await current_thread.send(f"❌ **Error processing message:** {str(e)}")
            finally:
                current_thread = None
                current_ticket_id = None
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
        
        # Store the current ticket ID globally for the handlers
        current_ticket_id = ticket_id
        
        # Create a new thread for this ticket
        current_thread = await message.create_thread(
            name=f"🎫 Ticket #{ticket_id[:8]}",
            auto_archive_duration=60  # Archive after 1 hour of inactivity
        )

        # Track the relationship between thread and ticket
        thread_to_ticket[str(current_thread.id)] = ticket_id
        ticket_to_thread[ticket_id] = current_thread

        # Use the Discord user's info
        customer_name = message.author.display_name or message.author.name
        customer_email = f"{message.author.id}@discord"

        # Send initial message to thread
        await current_thread.send(f"**Ticket #{ticket_id[:16]}** - Processing your request...")
        
        # Generate a smart summary for the thread name using OpenAI
        thread_name = await generate_thread_summary(agent_manager, content)
        print(f"{ticket_id}: {thread_name}")

        # Process the initial message
        try:
            response = await agent_manager.process_message(
                ticket_id, 
                customer_name, 
                customer_email, 
                content
            )
            
            if response:
                await current_thread.send(f"**Response:**\n{response}")
                
        except Exception as e:
            await current_thread.send(f"❌ **Error processing request:** {str(e)}")
        finally:
            # Clear the current thread and ticket ID references
            current_thread = None
            current_ticket_id = None


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
