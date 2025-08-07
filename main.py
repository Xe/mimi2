import uuid6
import asyncio
from agent import AgentManager


# Example usage
async def main():
    """
    Main function to run the agent.
    """
    agent_manager = AgentManager()
    ticket_id = str(uuid6.uuid7())
    customer_name = input("Customer name: ")
    customer_email = input("Customer email: ")
    
    print(f"Created ticket: {ticket_id}")
    
    while True:
        user_message = input("\nCustomer message (or 'quit' to exit): ")
        if user_message.lower() == 'quit':
            break
            
        response = await agent_manager.process_message(
            ticket_id, customer_name, customer_email, user_message
        )
        print("\n--- Agent Response ---\n")
        print(response)


if __name__ == "__main__":
    asyncio.run(main())

