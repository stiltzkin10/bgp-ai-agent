import struct
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, List

# BGP Message Types
OPEN = 1
UPDATE = 2
NOTIFICATION = 3
KEEPALIVE = 4


@dataclass
class BGPHeader:
    marker: bytes
    length: int
    type: int

    @staticmethod
    def pack(msg_type: int, payload: bytes = b"") -> bytes:
        """Packs a BGP message with header."""
        marker = b"\xff" * 16
        length = 19 + len(payload)
        return struct.pack("!16sHB", marker, length, msg_type) + payload

    @staticmethod
    def unpack(data: bytes) -> tuple["BGPHeader", bytes]:
        """Unpacks BGP header and returns (header, payload)."""
        if len(data) < 19:
            raise ValueError("Data too short for BGP header")
        marker, length, msg_type = struct.unpack("!16sHB", data[:19])
        if marker != b"\xff" * 16:
            raise ValueError("Invalid BGP marker")
        return BGPHeader(marker, length, msg_type), data[19:length]


class BGPMessage(ABC):
    msg_type: int

    @abstractmethod
    def pack(self) -> bytes:
        pass

    @classmethod
    @abstractmethod
    def unpack(cls, data: bytes) -> "BGPMessage":
        pass


@dataclass
class OpenMessage(BGPMessage):
    msg_type: ClassVar[int] = OPEN
    version: int
    my_as: int
    hold_time: int
    bgp_identifier: str  # IP string
    opt_params: bytes = b""

    def pack(self) -> bytes:
        bgp_id_int = struct.unpack("!I", socket.inet_aton(self.bgp_identifier))[0]
        payload = (
            struct.pack(
                "!BHHIB",
                self.version,
                self.my_as,
                self.hold_time,
                bgp_id_int,
                len(self.opt_params),
            )
            + self.opt_params
        )
        return BGPHeader.pack(self.msg_type, payload)

    @classmethod
    def unpack(cls, data: bytes) -> "OpenMessage":
        version, my_as, hold_time, bgp_id_int, opt_len = struct.unpack("!BHHIB", data[:10])
        bgp_identifier = socket.inet_ntoa(struct.pack("!I", bgp_id_int))
        opt_params = data[10 : 10 + opt_len]
        return cls(version, my_as, hold_time, bgp_identifier, opt_params)


@dataclass
class KeepAliveMessage(BGPMessage):
    msg_type: ClassVar[int] = KEEPALIVE

    def pack(self) -> bytes:
        return BGPHeader.pack(self.msg_type, b"")

    @classmethod
    def unpack(cls, data: bytes) -> "KeepAliveMessage":
        return cls()


@dataclass
class NotificationMessage(BGPMessage):
    msg_type: ClassVar[int] = NOTIFICATION
    error_code: int
    error_subcode: int
    data: bytes = b""

    def pack(self) -> bytes:
        payload = struct.pack("!BB", self.error_code, self.error_subcode) + self.data
        return BGPHeader.pack(self.msg_type, payload)

    @classmethod
    def unpack(cls, data: bytes) -> "NotificationMessage":
        error_code, error_subcode = struct.unpack("!BB", data[:2])
        return cls(error_code, error_subcode, data[2:])


@dataclass
class UpdateMessage(BGPMessage):
    msg_type: ClassVar[int] = UPDATE
    withdrawn_routes: bytes = b""
    path_attributes: bytes = b""
    nlri: bytes = b""

    # Note: Full parsing of UPDATE fields is complex.
    # For now we'll treat them as raw bytes in the container,
    # but the packing needs to follow the length fields structure.

    def pack(self) -> bytes:
        payload = struct.pack("!H", len(self.withdrawn_routes)) + self.withdrawn_routes
        payload += struct.pack("!H", len(self.path_attributes)) + self.path_attributes
        payload += self.nlri
        return BGPHeader.pack(self.msg_type, payload)

    @classmethod
    def unpack(cls, data: bytes) -> "UpdateMessage":
        offset = 0
        w_len = struct.unpack("!H", data[offset : offset + 2])[0]
        offset += 2
        withdrawn_routes = data[offset : offset + w_len]
        offset += w_len

        pa_len = struct.unpack("!H", data[offset : offset + 2])[0]
        offset += 2
        path_attributes = data[offset : offset + pa_len]
        offset += pa_len

        nlri = data[offset:]
        return cls(withdrawn_routes, path_attributes, nlri)

    @staticmethod
    def encode_nlri(prefixes: List[str]) -> bytes:
        """Encodes a list of prefixes (e.g., '10.0.0.0/24') into NLRI bytes."""
        nlri_bytes = b""
        for prefix in prefixes:
            ip_str, length_str = prefix.split("/")
            length = int(length_str)
            ip_int = struct.unpack("!I", socket.inet_aton(ip_str))[0]

            # Calculate bytes needed for the prefix
            # 24 -> 3 bytes, 25 -> 4 bytes
            num_bytes = (length + 7) // 8
            prefix_bytes = struct.pack("!I", ip_int)[:num_bytes]

            nlri_bytes += struct.pack("!B", length) + prefix_bytes
        return nlri_bytes

    @staticmethod
    def encode_origin(origin: int = 0) -> bytes:
        """Encodes ORIGIN attribute. 0=IGP, 1=EGP, 2=INCOMPLETE."""
        # Flag: 0x40 (Transitive)
        # Type: 1 (ORIGIN)
        # Length: 1
        return b"\x40\x01\x01" + struct.pack("!B", origin)

    @staticmethod
    def encode_as_path(asn_list: List[int]) -> bytes:
        """Encodes AS_PATH attribute. Supports AS_SEQUENCE only."""
        # Flag: 0x40 (Transitive)
        # Type: 2 (AS_PATH)
        if not asn_list:
            return b"\x40\x02\x00"

        # We use AS_SEQUENCE (2)
        # Segment Type: 2 (AS_SEQUENCE)
        # Segment Length: number of ASes
        path_data = b"\x02" + struct.pack("!B", len(asn_list))
        for asn in asn_list:
            path_data += struct.pack("!H", asn)  # 2-byte ASN for simplicity (BGP-4)

        length = len(path_data)
        return b"\x40\x02" + struct.pack("!B", length) + path_data

    @staticmethod
    def encode_next_hop(next_hop_ip: str) -> bytes:
        """Encodes NEXT_HOP attribute."""
        # Flag: 0x40 (Transitive)
        # Type: 3 (NEXT_HOP)
        # Length: 4
        return b"\x40\x03\x04" + socket.inet_aton(next_hop_ip)


def parse_bgp_message(header: BGPHeader, payload: bytes) -> BGPMessage:
    if header.type == OPEN:
        return OpenMessage.unpack(payload)
    elif header.type == UPDATE:
        return UpdateMessage.unpack(payload)
    elif header.type == NOTIFICATION:
        return NotificationMessage.unpack(payload)
    elif header.type == KEEPALIVE:
        return KeepAliveMessage.unpack(payload)
    else:
        raise ValueError(f"Unknown BGP message type: {header.type}")
