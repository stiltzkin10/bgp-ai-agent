import asyncio
import json
from typing import TYPE_CHECKING
from src.utils import setup_logging
from src.fsm import BGPState

if TYPE_CHECKING:
    from src.server import BGPServer


class ManagementServer:
    def __init__(self, bgp_server: "BGPServer", socket_path: str = "/tmp/bgp_agent.sock"):
        self.bgp_server = bgp_server
        self.socket_path = socket_path
        self.logger = setup_logging("MgmtServer")

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            data = await reader.read(4096)
            if not data:
                return

            request = json.loads(data.decode())
            command = request.get("command")

            response = {"status": "error", "message": "Unknown command"}

            if command == "show_neighbors":
                neighbors = []
                for session in self.bgp_server.sessions.values():
                    # Calculate uptime
                    uptime_str = "N/A"
                    if session.start_time and session.state == BGPState.ESTABLISHED:
                        import datetime

                        delta = datetime.datetime.now() - session.start_time
                        uptime_str = str(delta).split(".")[0]  # removing microseconds

                    neighbors.append(
                        {
                            "peer_ip": session.bgp_id,  # Assuming bgp_id is IP
                            "remote_as": session.remote_as or 0,
                            "state": session.state.name,
                            "uptime": uptime_str,
                            "msgs_sent": session.msgs_sent,
                            "msgs_received": session.msgs_received,
                        }
                    )
                response = {"status": "success", "data": neighbors}

            elif command == "show_routes_received":
                routes = []
                for session in self.bgp_server.sessions.values():
                    for route in session.adj_rib_in:
                        routes.append(
                            {
                                "prefix": route.prefix,
                                "next_hop": route.next_hop,
                                "as_path": str(route.as_path),
                                "origin": route.origin,
                                "remote_as": session.remote_as or 0,
                                "received_from": session.bgp_id,
                            }
                        )
                response = {"status": "success", "data": routes}

            elif command == "show_routes_advertised":
                # Currently we advertise same prefixes to all peers
                response = {
                    "status": "success",
                    "data": self.bgp_server.config.originated_prefixes,
                }

            writer.write(json.dumps(response).encode())
            await writer.drain()

        except Exception as e:
            self.logger.error(f"Error handling management request: {e}")
            error_response = {"status": "error", "message": str(e)}
            writer.write(json.dumps(error_response).encode())
            await writer.drain()
        finally:
            writer.close()

    async def start(self):
        import os

        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

        server = await asyncio.start_unix_server(self.handle_client, path=self.socket_path)
        self.logger.info(f"Management Server listening on {self.socket_path}")
        async with server:
            await server.serve_forever()
