import click
from tabulate import tabulate

from src.client import send_ipc_command

SOCKET_PATH = "/tmp/bgp_agent.sock"


def send_command(command: str):
    return send_ipc_command(SOCKET_PATH, command)


@click.group()
@click.option(
    "--socket",
    "socket_path",
    default="/tmp/bgp_agent.sock",
    help="Path to BGP agent socket",
)
@click.pass_context
def cli(ctx, socket_path):
    """BGP Agent Control CLI"""
    global SOCKET_PATH
    SOCKET_PATH = socket_path


@cli.group()
def show():
    """Show information"""
    pass


@show.command()
def neighbors():
    """Show BGP neighbors"""
    response = send_command("show_neighbors")
    if response["status"] == "success":
        data = response["data"]
        headers = ["Peer IP", "Remote AS", "State", "Uptime", "Msgs Sent", "Msgs Rcvd"]
        table = [
            [
                d["peer_ip"],
                d["remote_as"],
                d["state"],
                d["uptime"],
                d["msgs_sent"],
                d["msgs_received"],
            ]
            for d in data
        ]
        print(tabulate(table, headers=headers, tablefmt="grid"))
    else:
        click.echo(f"Error: {response.get('message')}", err=True)


@show.group(name="routes")
def routes_group():
    """Show routes"""
    pass


@routes_group.command(name="received")
def routes_received():
    """Show routes received from neighbors"""
    response = send_command("show_routes_received")
    if response["status"] == "success":
        data = response["data"]
        headers = [
            "Prefix",
            "Next Hop",
            "AS Path",
            "Origin",
            "Remote AS",
            "Received From",
        ]
        table = [
            [
                d["prefix"],
                d["next_hop"],
                d["as_path"],
                d["origin"],
                d["remote_as"],
                d["received_from"],
            ]
            for d in data
        ]
        print(tabulate(table, headers=headers, tablefmt="grid"))
    else:
        click.echo(f"Error: {response.get('message')}", err=True)


@routes_group.command(name="advertised")
def routes_advertised():
    """Show routes advertised to neighbors"""
    response = send_command("show_routes_advertised")
    if response["status"] == "success":
        data = response["data"]
        # Data is just a list of strings (prefixes)
        headers = ["Prefix"]
        table = [[p] for p in data]
        print(tabulate(table, headers=headers, tablefmt="grid"))
    else:
        click.echo(f"Error: {response.get('message')}", err=True)


if __name__ == "__main__":
    cli()
