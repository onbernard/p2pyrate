from asyncio import StreamReader, StreamWriter
from dataclasses import dataclass, field
import asyncio
import random

from .peer import (
    Choke,
    Unchoke,
    Interested,
    NotInterested,
    Have,
    Bitfield,
    Request,
    Piece,
    Cancel,
    Handshake,
    PeerMessage_T,
    read_message,
    write_message,
)
from .metadata import Metadata
from .utils import bl_to_bitfield, bitfield_to_bl


@dataclass
class Peer:
    host: str
    port: int
    has_piece: list[bool]
    _reader: StreamReader = field(repr=False)
    _writer: StreamWriter = field(repr=False)
    choked: bool = True
    interested: bool = False

    @classmethod
    def from_streams(cls, reader: StreamReader, writer: StreamWriter):
        addr = writer.get_extra_info("peername")
        return cls(
            host=addr[0],
            port=addr[1],
            has_piece=[],
            _reader=reader,
            _writer=writer,
        )

    async def handshake_in(self, info_hash: bytes, peer_id: bytes) -> Handshake:
        hs = await Handshake.from_reader(self._reader)
        self._writer.write(Handshake(info_hash=info_hash, peer_id=peer_id).to_bytes())
        await self._writer.drain()
        return hs

    async def handshake_out(self, info_hash: bytes, peer_id: bytes) -> Handshake:
        self._writer.write(Handshake(info_hash=info_hash, peer_id=peer_id).to_bytes())
        await self._writer.drain()
        hs = await Handshake.from_reader(self._reader)
        return hs

    async def read(self) -> PeerMessage_T:
        return await read_message(self._reader)
    
    async def write(self, message: PeerMessage_T):
        return await write_message(self._writer, message)

    async def close(self):
        self._writer.close()
        await self._writer.wait_closed()


@dataclass
class TorrentPiece:
    hash: bytes
    have: bool = False
    data: bytes = b""


class Downloader:
    def __init__(self, metadata: Metadata, peer_id: bytes|None=None) -> None:
        if peer_id is None:
            peer_id = ("XX-" + "".join(f"{random.randint(0,9)}" for _ in range(17))).encode("utf-8")
        self.metadata = metadata
        self.peer_id: bytes = peer_id
        self.info_hash: bytes = metadata.info.hash
        self.trackers = [metadata.announce.decode(),*[a[0].decode() for a in metadata[b"announce-list"]]]
        self.peers: list[Peer] = []
        self.pieces: list[TorrentPiece] = [TorrentPiece(hash=p) for p in metadata.info.pieces]


    @property
    def have_list(self) -> list[bool]:
        return [p.have for p in self.pieces]

    async def handle_peer_outbound(self, peer: Peer):
        _ = await peer.handshake_out(self.info_hash, self.peer_id)
        if any(self.have_list):
            await peer.write(Bitfield(payload=bl_to_bitfield(self.have_list)))
        while True:
            message = await peer.read()
            match message:
                case Choke():
                    peer.choked = True
                case Unchoke():
                    peer.choked = False
                case Interested():
                    ...
                case NotInterested():
                    ...
                case Have() as m:
                    ...
                case Bitfield(payload):
                    peer.has_piece = bitfield_to_bl(payload)
                case Request() as m:
                    ...
                case Piece() as m:
                    ...
                case Cancel() as m:
                    ...
                case _ as m:
                    raise ValueError(f"unexpected message {m}")
        await peer.close()

    async def handle_peer_inbound(self, peer: Peer):
        _ = await peer.handshake_in(self.info_hash, self.peer_id)
        #
        while True:
            ...
        #
        await peer.close()

    async def start_server(self, port: int|None=None):
        server = await asyncio.start_server(
            lambda r,w: self.handle_peer_inbound(Peer.from_streams(r,w)), '127.0.0.1', port
        )
        addr = server.sockets[0].getsockname()
        print(f'Listening on {addr}')
        async with server:
            await server.serve_forever()
