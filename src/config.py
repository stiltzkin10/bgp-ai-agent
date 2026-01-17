import yaml
from pydantic import BaseModel, Field
from typing import List


class LocalConfig(BaseModel):
    asn: int
    router_id: str
    port: int = 179
    socket_path: str = "/tmp/bgp_agent.sock"


class PeerConfig(BaseModel):
    ip: str
    port: int = 179
    remote_as: int
    hold_time: int = 180


class BGPConfig(BaseModel):
    local: LocalConfig
    peers: List[PeerConfig] = Field(default_factory=list)
    originated_prefixes: List[str] = Field(default_factory=list)


def load_config(path: str) -> BGPConfig:
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return BGPConfig(**data)
