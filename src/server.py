import asyncio
from typing import Optional
from src.session import BGPSession
from src.utils import setup_logging
from src.config import BGPConfig
from src.mgmt import ManagementServer


class BGPServer:
    def __init__(self, config: BGPConfig):
        self.config = config
        self.logger = setup_logging("BGPServer")
        self.server: Optional[asyncio.AbstractServer] = None
        self.sessions = {}  # Keep track of sessions
        self.mgmt_server = ManagementServer(self, socket_path=config.local.socket_path)

        self.logger.info(f"Initialized BGP Server with ASN {config.local.asn}, Router ID {config.local.router_id}")

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer_addr = writer.get_extra_info("peername")
        peer_ip = peer_addr[0]
        self.logger.info(f"Accepted connection from {peer_addr}")

        # Check existing session
        if peer_ip in self.sessions:
            self.logger.warning(f"Session for {peer_ip} already exists. Ignoring new connection.")
            writer.close()
            return

        peer_config = None
        for p in self.config.peers:
            if p.ip == peer_ip:
                peer_config = p
                break

        if not peer_config:
            self.logger.warning(f"Connection from unknown peer {peer_ip}. Closing.")
            writer.close()
            return

        hold_time = peer_config.hold_time

        # Create a new session for this peer
        session = BGPSession(
            self.config.local.asn,
            self.config.local.router_id,
            peer_ip,  # Pass peer IP
            hold_time,
            self.config.originated_prefixes,
        )
        self.sessions[peer_ip] = session

        await session.connection_made(reader, writer)

    async def start(self):
        self.server = await asyncio.start_server(self.handle_client, "0.0.0.0", self.config.local.port)
        addr = self.server.sockets[0].getsockname()
        self.logger.info(f"BGP Speaker listening on {addr}")

        # Start Management Server
        asyncio.create_task(self.mgmt_server.start())

        # Initiate connections to peers
        for peer in self.config.peers:
            asyncio.create_task(self.connect_peer(peer.ip, peer.port, peer.hold_time))

        async with self.server:
            await self.server.serve_forever()

    async def connect_peer(self, peer_ip: str, peer_port: int, hold_time: int):
        self.logger.info(f"Initiating connection to {peer_ip}:{peer_port}")
        # Simple retry loop
        while True:
            if peer_ip in self.sessions:
                # Session might be active or connecting.
                # For now, if we have an object, we assume it's handling it or it came from accept().
                # We should stop trying if we accepted a connection.
                # But we need to distinguish state.
                # Let's check state.
                session = self.sessions[peer_ip]
                if (
                    session.state != "IDLE"
                ):  # Using string comparion or import Enum? Enum is better but string for now if lazy? No, let's just abort this loop if session exists.
                    # But we might need to reconnect if it goes to IDLE?
                    # A real implementation implies a complex state machine for the connection itself.
                    # Simplified: If entry exists, wait.
                    await asyncio.sleep(5)
                    continue

            try:
                reader, writer = await asyncio.open_connection(peer_ip, peer_port)
                self.logger.info(f"Connected to {peer_ip}:{peer_port}")

                # Check race condition again
                if peer_ip in self.sessions:
                    writer.close()
                    await asyncio.sleep(5)
                    continue

                session = BGPSession(
                    self.config.local.asn,
                    self.config.local.router_id,
                    peer_ip,
                    hold_time,
                    self.config.originated_prefixes,
                )
                self.sessions[peer_ip] = session
                await session.connection_made(reader, writer)
                return
            except Exception as e:
                self.logger.error(f"Failed to connect to {peer_ip}:{peer_port}: {e}. Retrying in 5s...")
                await asyncio.sleep(5)
