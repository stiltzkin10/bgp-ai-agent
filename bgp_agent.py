import click
from dotenv import load_dotenv
from google import genai
from google.genai import types
from src.client import send_ipc_command

# Load environment variables
load_dotenv()

SOCKET_PATH = "/tmp/bgp_agent.sock"


# Tool Definitions
def get_neighbor_stats() -> list:
    """Queries the IPC socket to get a list of all neighbors, their ASNs, and states.

    Returns:
        A list of neighbor dictionaries with keys: peer_ip, remote_as, state, uptime, msgs_sent, msgs_received
    """
    response = send_ipc_command(SOCKET_PATH, "show_neighbors")
    if response["status"] == "success":
        return response["data"]
    return []


def get_routes_received(peer_ip: str = None) -> list:
    """Fetches routes from the Adj-RIB-In.

    Args:
        peer_ip: Optional peer IP address to filter routes. If not provided, returns all routes.

    Returns:
        A list of route dictionaries with keys: prefix, next_hop, as_path, origin, remote_as, received_from
    """
    response = send_ipc_command(SOCKET_PATH, "show_routes_received")
    if response["status"] == "success":
        data = response["data"]
        if peer_ip:
            data = [r for r in data if r["received_from"] == peer_ip]
        return data
    return []


def get_routes_advertised() -> list:
    """Fetches prefixes in the Adj-RIB-Out (routes we are advertising).

    Returns:
        A list of prefix strings that are being advertised.
    """
    response = send_ipc_command(SOCKET_PATH, "show_routes_advertised")
    if response["status"] == "success":
        return response["data"]
    return []


def count_unique_routers_in_asn(asn: int) -> int:
    """Counts how many peers belong to a specific ASN.

    Args:
        asn: The Autonomous System Number to filter by.

    Returns:
        The number of peers with the specified remote ASN.
    """
    neighbors = get_neighbor_stats()
    count = 0
    for n in neighbors:
        if n["remote_as"] == asn:
            count += 1
    return count


SYSTEM_INSTRUCTION = """You are a senior Network Operations Center (NOC) engineer.
Use the provided tools to inspect the BGP RIB and neighbor states before answering user questions.
Always check the neighbor status before assuming routes are exchanging.
When asked about routes, use get_routes_received or get_routes_advertised as appropriate.
Provide concise, accurate answers based on the actual data from the tools.
"""


@click.command()
@click.option("--socket", default="/tmp/bgp_agent.sock", help="Path to BGP agent socket")
@click.option("--api-key", envvar="GEMINI_API_KEY", help="Gemini API Key")
def run_agent(socket, api_key):
    """Run the AI Network Analyst Agent."""
    global SOCKET_PATH
    SOCKET_PATH = socket

    if not api_key:
        click.echo("Error: GEMINI_API_KEY not found. Set it in .env or pass --api-key.")
        return

    # Create client with API key
    client = genai.Client(api_key=api_key)

    print("--- AI Network Analyst (Type 'exit' to quit) ---")

    # Maintain conversation history
    history = []

    while True:
        try:
            user_input = input(">: ")
            if user_input.lower() in ["exit", "quit"]:
                break

            # Add user message to history
            history.append(types.Content(role="user", parts=[types.Part.from_text(text=user_input)]))

            # Generate content with tools
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=history,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=[
                        get_neighbor_stats,
                        get_routes_received,
                        get_routes_advertised,
                        count_unique_routers_in_asn,
                    ],
                ),
            )

            # Add model response to history
            if response.candidates and response.candidates[0].content:
                history.append(response.candidates[0].content)

            print(f"Agent: {response.text}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    run_agent()
