from asyncio import StreamReader, StreamWriter
from dataclasses import dataclass, field
import struct

from loguru import logger as log

from .handshake import Handshake
from .message import (
    Choke,
    Unchoke,
    Interested,
    NotInterested,
    Have,
    Bitfield,
    Request,
    Piece,
    Cancel,
    PeerMessage_T,
)


@dataclass
class Peer:
    host: str
    port: int
    _reader: StreamReader = field(repr=False)
    _writer: StreamWriter = field(repr=False)
    peer_id: bytes|None = None
    choked: bool = True
    interested: bool = False
    pieces: set[int] = field(repr=False, default_factory=lambda: set())


    @classmethod
    def from_streams(cls, reader: StreamReader, writer: StreamWriter):
        addr = writer.get_extra_info("peername")
        return cls(
            host=addr[0],
            port=addr[1],
            _reader=reader,
            _writer=writer,
        )

    async def handshake(self, info_hash: bytes, peer_id: bytes, outbound: bool) -> Handshake:
        if outbound:
            hs = await self.send_handshake(info_hash=info_hash, peer_id=peer_id)
        else:
            hs = await self.receive_handshake(info_hash=info_hash, peer_id=peer_id)
        self.peer_id = hs.peer_id
        return hs

    async def receive_handshake(self, info_hash: bytes, peer_id: bytes) -> Handshake:
        hs = await Handshake.from_reader(self._reader)
        self._writer.write(Handshake(info_hash=info_hash, peer_id=peer_id).to_bytes())
        await self._writer.drain()
        return hs

    async def send_handshake(self, info_hash: bytes, peer_id: bytes) -> Handshake:
        self._writer.write(Handshake(info_hash=info_hash, peer_id=peer_id).to_bytes())
        await self._writer.drain()
        hs = await Handshake.from_reader(self._reader)
        return hs

    async def choke(self):
        await self.write(Choke())
        self.choked = True

    async def unchoke(self):
        await self.write(Unchoke())
        self.choked = False

    async def send_bitfield(self, have: list[bool]):
        await self.write(Bitfield.from_bool_list(have))

    async def read(self) -> PeerMessage_T:
        message = await read_message(self._reader)
        log.debug(f"read {message.message_id} from {self.peer_id}")
        return message
    
    async def write(self, message: PeerMessage_T):
        log.debug(f"write {message.message_id} to {self.peer_id}")
        return await write_message(self._writer, message)

    async def close(self):
        self._writer.close()
        await self._writer.wait_closed()


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
