from enum import Enum, auto


class BGPState(Enum):
    IDLE = auto()
    CONNECT = auto()
    ACTIVE = auto()
    OPEN_SENT = auto()
    OPEN_CONFIRM = auto()
    ESTABLISHED = auto()


class BGPEvent(Enum):
    # Administrative events
    MANUAL_START = auto()
    MANUAL_STOP = auto()

    # TCP Connection events
    TCP_CONNECTION_CONFIRMED = auto()
    TCP_CONNECTION_FAIL = auto()

    # BGP Message events
    BGPOPEN = auto()
    BGPHEADERERR = auto()
    OPEN_COLLISION_DUMP = auto()
    NOTIF_MSG_VER_ERR = auto()
    NOTIF_MSG = auto()
    KEEPALIVE_MSG = auto()
    UPDATE_MSG = auto()
    UPDATE_MSG_ERR = auto()

    # Timer events
    CONNECT_RETRY_TIMER_EXPIRES = auto()
    HOLD_TIMER_EXPIRES = auto()
    KEEPALIVE_TIMER_EXPIRES = auto()
