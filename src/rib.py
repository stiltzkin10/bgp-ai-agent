from dataclasses import dataclass
from typing import List


@dataclass
class Route:
    prefix: str
    next_hop: str
    as_path: List[int]
    origin: str
