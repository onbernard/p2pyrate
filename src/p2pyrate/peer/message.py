from typing import (
    Literal,
    Self,
)
from dataclasses import dataclass
import struct

from ..utils import bitfield_to_bl, bl_to_bitfield

__all__ = ["Choke", "Unchoke", "Interested", "NotInterested", "Have", "Bitfield", "Request", "Piece", "Cancel", "PeerMessage_T"]


@dataclass
class Choke:
    payload: Literal[b""] = b""
    message_id: Literal[0] = 0

@dataclass
class Unchoke:
    payload: Literal[b""] = b""
    message_id: Literal[1] = 1

@dataclass
class Interested:
    payload: Literal[b""] = b""
    message_id: Literal[2] = 2

@dataclass
class NotInterested:
    payload: Literal[b""] = b""
    message_id: Literal[3] = 3

@dataclass
class Have:
    payload: bytes
    message_id: Literal[4] = 4

    @classmethod
    def from_index(cls, index: int) -> Self:
        return cls(
            payload=struct.pack("!I", index)
        )

    @property
    def index(self) -> int:
        return struct.unpack("!I", self.payload)[0]


@dataclass
class Bitfield:
    payload: bytes
    message_id: Literal[5] = 5

    @classmethod
    def from_bool_list(cls, bool_list: list[bool]) -> Self:
        return cls(
            payload=bl_to_bitfield(bool_list)
        )

    @property
    def bool_list(self) -> list[bool]:
        return bitfield_to_bl(self.payload)


@dataclass
class Request:
    payload: bytes
    message_id: Literal[6] = 6

    @classmethod
    def from_block(cls, index, begin, length) -> Self:
        return cls(
            payload=struct.pack("!III", index, begin, length)
        )

    @property
    def data(self) -> tuple[int,int,int]:
        return struct.unpack("!III", self.payload)

@dataclass
class Piece:
    payload: bytes
    message_id: Literal[7] = 7

    @classmethod
    def from_block(cls, index: int, begin: int, block: bytes) -> Self:
        return cls(
            payload=struct.pack("!II", index, begin) + block
        )
    
    @property
    def data(self) -> tuple[int,int,bytes]:
        assert len(self.payload) > 8
        index, begin = struct.unpack("!II", self.payload[:8])
        return index, begin, self.payload[8:]


@dataclass
class Cancel:
    payload: bytes
    message_id: Literal[8] = 8

    @property
    def message(self) -> tuple[int,int,int]:
        ...


PeerMessage_T = Choke|Unchoke|Interested|NotInterested|Have|Bitfield|Request|Piece|Cancel
