from typing import (
    Literal,
)
from asyncio import StreamReader, StreamWriter
from dataclasses import dataclass
import struct


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

    @property
    def message(self) -> int:
        ...

@dataclass
class Bitfield:
    payload: bytes
    message_id: Literal[5] = 5

@dataclass
class Request:
    payload: bytes
    message_id: Literal[6] = 6

    @property
    def message(self) -> tuple[int,int,int]:
        ...

@dataclass
class Piece:
    payload: bytes
    message_id: Literal[7] = 7

    @property
    def message(self) -> tuple[int,int,bytes]:
        ...


@dataclass
class Cancel:
    payload: bytes
    message_id: Literal[8] = 8

    @property
    def message(self) -> tuple[int,int,int]:
        ...

PeerMessage_T = Choke|Unchoke|Interested|NotInterested|Have|Bitfield|Request|Piece|Cancel


async def read_message(reader: StreamReader) -> PeerMessage_T:
    buf = await reader.readexactly(4)
    m_len = struct.unpack("!I", buf[:4])[0]
    buf = await reader.readexactly(m_len)
    message_id = struct.unpack("!B", buf[:1])[0]
    payload = buf[1:]
    match message_id:
        case 0:
            return Choke()
        case 1:
            return Unchoke()
        case 2:
            return Interested()
        case 3:
            return NotInterested()
        case 4:
            return Have(payload=payload)
        case 5:
            return Bitfield(payload=payload)
        case 6:
            return Request(payload=payload)
        case 7:
            return Piece(payload=payload)
        case 8:
            return Cancel(payload=payload)
        case _:
            raise ValueError(f"unexpected message id: {message_id}")


async def write_message(writer: StreamWriter, message: PeerMessage_T):
    m_len = len(message.payload) +1
    writer.write(struct.pack(f"!IB{len(message.payload)}s", m_len, message.message_id, message.payload))
    await writer.drain()
