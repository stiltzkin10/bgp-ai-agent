import asyncio
from typing import Optional

from src.protocol import (
    BGPHeader,
    BGPMessage,
    OpenMessage,
    KeepAliveMessage,
    NotificationMessage,
    UpdateMessage,
    parse_bgp_message,
)
from src.fsm import BGPState
from src.utils import setup_logging


from datetime import datetime
from src.rib import Route
import struct


class BGPSession:
    def __init__(
        self,
        my_as: int,
        bgp_id: str,
        peer_ip: str,
        hold_time: int = 240,
        originated_prefixes: Optional[list[str]] = None,
    ):
        self.state = BGPState.IDLE
        self.my_as = my_as
        self.bgp_id = bgp_id
        self.peer_ip = peer_ip
        self.hold_time = hold_time  # Configured hold time
        self.originated_prefixes = originated_prefixes or []
        self.negotiated_hold_time = 0

        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.peer_header: Optional[dict] = None  # Stores remote_as from OPEN

        self.keepalive_timer_task: Optional[asyncio.Task] = None
        self.hold_timer_task: Optional[asyncio.Task] = None
        self.hold_timer_reset_event = asyncio.Event()

        self.logger = setup_logging(f"BGPSession-{self.bgp_id}")

        # Stats
        self.msgs_sent = 0
        self.msgs_received = 0
        self.start_time = None
        self.remote_as = None

        # RIB
        self.adj_rib_in: list[Route] = []

    async def connection_made(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.start_time = datetime.now()
        self.logger.info("TCP Connection established")

        # Simplified: Force transition to OPEN_SENT and send OPEN
        self.state = BGPState.OPEN_SENT
        await self.send_open()

        # Start reading loop
        await self.handle_incoming_messages()

    async def send_message(self, message: BGPMessage):
        data = message.pack()
        if self.writer:
            self.writer.write(data)
            await self.writer.drain()
            self.msgs_sent += 1

    async def send_open(self):
        self.logger.info("Sending OPEN message")
        msg = OpenMessage(
            version=4,
            my_as=self.my_as,
            hold_time=self.hold_time,
            bgp_identifier=self.bgp_id,
        )
        await self.send_message(msg)

    async def send_update(self):
        """Sends an UPDATE message with originated prefixes."""
        if not self.originated_prefixes:
            return

        self.logger.info(f"Sending UPDATE with prefixes: {self.originated_prefixes}")

        # Construct Attributes
        path_attributes = b""

        # ORIGIN: IGP
        path_attributes += UpdateMessage.encode_origin(0)

        # AS_PATH: Empty (local origination)
        path_attributes += UpdateMessage.encode_as_path([self.my_as])

        # NEXT_HOP: Self
        path_attributes += UpdateMessage.encode_next_hop(self.bgp_id)

        # NLRI
        nlri = UpdateMessage.encode_nlri(self.originated_prefixes)

        msg = UpdateMessage(withdrawn_routes=b"", path_attributes=path_attributes, nlri=nlri)
        await self.send_message(msg)

    async def send_keepalive(self):
        # self.logger.debug("Sending KEEPALIVE")
        msg = KeepAliveMessage()
        await self.send_message(msg)

    async def send_notification(self, error_code, error_subcode, data=b""):
        self.logger.error(f"Sending NOTIFICATION: {error_code}, {error_subcode}")
        msg = NotificationMessage(error_code, error_subcode, data)
        await self.send_message(msg)
        self.close_connection()

    def close_connection(self):
        self.logger.info("Closing connection")
        if self.writer:
            self.writer.close()
            # Stop timers
            if self.keepalive_timer_task:
                self.keepalive_timer_task.cancel()
            if self.hold_timer_task:
                self.hold_timer_task.cancel()
            self.state = BGPState.IDLE

    async def handle_incoming_messages(self):
        try:
            while True:
                # Read Header
                # 16 marker + 2 len + 1 type
                header_bytes = await self.reader.readexactly(19)
                try:
                    header, _ = BGPHeader.unpack(header_bytes)
                except Exception as e:
                    self.logger.error(f"Header Error: {e}")
                    # Header Error (1), Synchronization Error (invalid marker?)
                    # Need to implement specific error handling
                    await self.send_notification(1, 1)
                    return

                payload_len = header.length - 19
                if payload_len > 0:
                    payload = await self.reader.readexactly(payload_len)
                else:
                    payload = b""

                try:
                    msg = parse_bgp_message(header, payload)
                except Exception as e:
                    self.logger.error(f"Message Parse Error: {e}")
                    # Malformed Message?
                    return

                await self.process_message(msg)

        except asyncio.IncompleteReadError:
            self.logger.info("Peer closed connection")
            self.close_connection()
        except ConnectionResetError:
            self.logger.info("Connection reset by peer")
            self.close_connection()
        except Exception as e:
            self.logger.error(f"Unexpected error in read loop: {e}")
            self.close_connection()

    async def process_message(self, msg: BGPMessage):
        self.msgs_received += 1
        self.logger.info(f"Received message: {msg.msg_type} in State: {self.state}")

        # Reset Hold Timer
        self.hold_timer_reset_event.set()

        if self.state == BGPState.OPEN_SENT:
            if isinstance(msg, OpenMessage):
                if msg.hold_time < self.hold_time:
                    self.negotiated_hold_time = msg.hold_time
                else:
                    self.negotiated_hold_time = self.hold_time

                self.remote_as = msg.my_as
                self.logger.info(f"Negotiated Hold Time: {self.negotiated_hold_time}, Remote AS: {self.remote_as}")

                await self.send_keepalive()
                self.state = BGPState.OPEN_CONFIRM

                if self.negotiated_hold_time > 0:
                    self.keepalive_timer_task = asyncio.create_task(self.keepalive_loop())
                    self.hold_timer_task = asyncio.create_task(self.hold_timer_loop())

            elif isinstance(msg, NotificationMessage):
                self.logger.error(f"Received Notification in OPEN_SENT: {msg}")
                self.close_connection()
            else:
                self.logger.error(f"Received unexpected message in OPEN_SENT: {msg}")
                await self.send_notification(5, 1)

        elif self.state == BGPState.OPEN_CONFIRM:
            if isinstance(msg, KeepAliveMessage):
                self.state = BGPState.ESTABLISHED
                self.logger.info("BGP Session ESTABLISHED")
                await self.send_update()
            elif isinstance(msg, NotificationMessage):
                self.close_connection()
            elif isinstance(msg, OpenMessage):
                await self.send_notification(5, 1)

        elif self.state == BGPState.ESTABLISHED:
            if isinstance(msg, UpdateMessage):
                self.logger.info(f"Received UPDATE: {len(msg.nlri)} bytes NLRI")
                self.handle_update_msg(msg)
            elif isinstance(msg, KeepAliveMessage):
                pass
            elif isinstance(msg, NotificationMessage):
                self.logger.info(f"Received Notification: {msg}")
                self.close_connection()
            else:
                self.logger.error(f"Unexpected message in ESTABLISHED: {msg}")

    def handle_update_msg(self, msg: UpdateMessage):
        # Very basic parsing for demo
        # Parse NLRI
        prefixes = []
        data = msg.nlri
        idx = 0
        while idx < len(data):
            length = data[idx]
            idx += 1
            num_bytes = (length + 7) // 8
            prefix_bytes = data[idx : idx + num_bytes]
            idx += num_bytes

            # Pad to 4 bytes for valid ipv4 conversion
            padded = prefix_bytes + b"\x00" * (4 - len(prefix_bytes))
            import socket

            ip_str = socket.inet_ntoa(padded)
            prefixes.append(f"{ip_str}/{length}")

        # Parse basic attributes to find NEXT_HOP
        next_hop = "Unknown"
        as_path = []

        # This parsing is extremely simplified and brittle, purely for the demo requirement
        # A real parser would iterate over path attributes properly via TLV.
        # We can try to scan for NEXT_HOP (Type 3)
        pa = msg.path_attributes
        pidx = 0
        while pidx < len(pa):
            flags = pa[pidx]
            type_code = pa[pidx + 1]
            pidx += 2

            # Check extended length flag (0x10)
            if flags & 0x10:
                attr_len = struct.unpack("!H", pa[pidx : pidx + 2])[0]
                pidx += 2
            else:
                attr_len = pa[pidx]
                pidx += 1

            attr_val = pa[pidx : pidx + attr_len]

            if type_code == 3:  # NEXT_HOP
                import socket

                next_hop = socket.inet_ntoa(attr_val)
            elif type_code == 2:  # AS_PATH
                # Parse AS Sequence if possible
                pass

            pidx += attr_len

        for p in prefixes:
            self.adj_rib_in.append(Route(prefix=p, next_hop=next_hop, as_path=[], origin="IGP"))

        self.logger.info(f"Updated RIB with routes: {prefixes}")

    async def keepalive_loop(self):
        """Sends Keepalives at 1/3 of the hold time."""
        interval = self.negotiated_hold_time / 3
        try:
            while True:
                await asyncio.sleep(interval)
                if self.state in [BGPState.OPEN_CONFIRM, BGPState.ESTABLISHED]:
                    await self.send_keepalive()
        except asyncio.CancelledError:
            pass

    async def hold_timer_loop(self):
        """Checks if no message received within hold time."""
        try:
            while True:
                self.hold_timer_reset_event.clear()
                try:
                    await asyncio.wait_for(
                        self.hold_timer_reset_event.wait(),
                        timeout=self.negotiated_hold_time,
                    )
                except asyncio.TimeoutError:
                    self.logger.error("Hold Timer Expired")
                    await self.send_notification(4, 0)  # Hold Timer Expired
                    return
        except asyncio.CancelledError:
            pass
