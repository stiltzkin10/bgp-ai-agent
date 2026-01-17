import struct
from src.protocol import (
    BGPHeader,
    OpenMessage,
    NotificationMessage,
    UpdateMessage,
    OPEN,
    UPDATE,
    NOTIFICATION,
    KEEPALIVE,
)


def test_bgp_header_pack():
    header = BGPHeader.pack(OPEN, b"1234")
    assert len(header) == 23  # 19 + 4
    assert header[:16] == b"\xff" * 16
    assert header[18] == OPEN


def test_bgp_header_unpack():
    data = b"\xff" * 16 + struct.pack("!HB", 19, KEEPALIVE)
    header, payload = BGPHeader.unpack(data)
    assert header.type == KEEPALIVE
    assert header.length == 19
    assert payload == b""


def test_open_message():
    msg = OpenMessage(4, 65001, 180, "192.168.1.1")
    packed = msg.pack()

    header, payload = BGPHeader.unpack(packed)
    assert header.type == OPEN

    unpacked = OpenMessage.unpack(payload)
    assert unpacked.version == 4
    assert unpacked.my_as == 65001
    assert unpacked.hold_time == 180
    assert unpacked.bgp_identifier == "192.168.1.1"


def test_notification_message():
    msg = NotificationMessage(1, 2, b"Error")
    packed = msg.pack()

    header, payload = BGPHeader.unpack(packed)
    assert header.type == NOTIFICATION

    unpacked = NotificationMessage.unpack(payload)
    assert unpacked.error_code == 1
    assert unpacked.error_subcode == 2
    assert unpacked.data == b"Error"


def test_update_message_empty():
    msg = UpdateMessage()
    packed = msg.pack()

    header, payload = BGPHeader.unpack(packed)
    assert header.type == UPDATE

    unpacked = UpdateMessage.unpack(payload)
    assert unpacked.withdrawn_routes == b""
    assert unpacked.path_attributes == b""
    assert unpacked.nlri == b""
