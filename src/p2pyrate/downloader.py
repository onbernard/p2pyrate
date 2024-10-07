from dataclasses import dataclass
from itertools import batched
from hashlib import sha1
import asyncio
import random

from loguru import logger as log

from .metadata import Metadata
from .peer.peer import Peer
import p2pyrate.peer.message as pm



class TorrentPiece:
    def __init__(self, index: int, hash: bytes, size: int) -> None:
        self.index = index
        self.hash: bytes = hash
        self.size: int = size
        self.data: bytearray = bytearray(b"\x00" * size)
        self.missing: list[bool] = [True] * size

    @property
    def complete(self) -> bool:
        return not any(self.missing)

    def set_complete_data(self, data: bytes):
        assert sha1(data).digest()==self.hash
        self.data = bytearray(data)
        self.missing = [False] * self.size

    def add_block(self, begin: int, block: bytes):
        assert begin+len(block) <= self.size
        self.data[begin:begin+len(block)] = block
        self.missing[begin:begin+len(block)] = [False] * len(block)

    def missing_blocks(self, block_size: int=64*2**3) -> list[tuple[int,int,int]]:
        outp = []
        for i,b in enumerate(batched(self.missing, block_size)):
            if any(b):
                outp.append((self.index,i*block_size,block_size))
        return outp


@dataclass
class CompletePiece:
    index: int

ClientEvent_T = CompletePiece

@dataclass
class Event:
    peer_id: bytes
    message: pm.PeerMessage_T|ClientEvent_T

    

class Downloader:
    def __init__(self, metadata: Metadata, peer_id: bytes|None=None) -> None:
        if peer_id is None:
            peer_id = ("XX-" + "".join(f"{random.randint(0,9)}" for _ in range(17))).encode("utf-8")
        self.metadata = metadata
        self.peer_id: bytes = peer_id
        self.info_hash: bytes = metadata.info.hash
        self.piece_length: int = metadata.info.piece_length
        self.trackers = [metadata.announce.decode(),*[a[0].decode() for a in metadata[b"announce-list"]]]
        self.peers: dict[bytes,Peer] = {}
        self.pieces: list[TorrentPiece] = [TorrentPiece(index=idx, hash=p, size=self.piece_length) for idx,p in enumerate(metadata.info.pieces)]
        self.event_q: asyncio.Queue[Event] = asyncio.Queue()

    @property
    def have(self) -> list[bool]:
        return [p.complete for p in self.pieces]


    async def handle_peer(self, peer: Peer, outbound: bool):
        log.info(f"connection made to {peer}")
        hs = await peer.handshake(self.info_hash, self.peer_id, outbound)
        log.info(f"handshake made to {peer}")
        assert hs.info_hash == self.info_hash
        assert peer.peer_id is not None
        self.peers[peer.peer_id] = peer
        if any(self.have):
            await peer.send_bitfield(self.have)
        await peer.unchoke()
        while True:
            message = await peer.read()
            await self.event_q.put(Event(peer_id=peer.peer_id, message=message))
        await peer.close()


    async def handle_events(self):
        while True:
            e = await self.event_q.get()
            peer = self.peers.get(e.peer_id)
            # Client Events
            if peer is None:
                match e.message:
                    case CompletePiece(index):
                        if all(p.complete for p in self.pieces):
                            return
                        await asyncio.gather(*(p.write(pm.Have.from_index(index)) for p in self.peers.values()))
                    
                    case _ as m:
                        raise ValueError(f"unexpected message {m}")

                continue
            # Peer events
            match e.message:
                case pm.Choke():
                    peer.choked = True

                case pm.Unchoke():
                    peer.choked = False
                    for idx in peer.pieces:
                        if not (piece := self.pieces[idx]).complete:
                            for b in piece.missing_blocks():
                                await peer.write(pm.Request.from_block(*b))

                case pm.Interested:
                    peer.interested = True

                case pm.NotInterested:
                    peer.interested = False

                case pm.Have() as m:
                    peer.pieces.add(m.index)
                    if not (piece := self.pieces[m.index]).complete:
                        if peer.choked:
                            await peer.write(pm.Interested())
                        else:
                            for b in piece.missing_blocks():
                                await peer.write(pm.Request.from_block(*b))

                case pm.Bitfield() as m:
                    for index,has in enumerate(m.bool_list[:len(self.pieces)]):
                        if has:
                            peer.pieces.add(index)
                    if any((not self.pieces[idx].complete) for idx in peer.pieces):
                        if peer.choked:
                            await peer.write(pm.Interested())
                        else:
                            for idx in peer.pieces:
                                if not (piece := self.pieces[idx]).complete:
                                    for b in piece.missing_blocks():
                                        await peer.write(pm.Request.from_block(*b))

                case pm.Request() as m:
                    index, begin, size = m.data
                    if not self.pieces[index].missing[begin]:
                        piece = self.pieces[index]
                        await peer.write(pm.Piece.from_block(index, begin, piece.data[begin:begin+piece.size]))
                    

                case pm.Piece() as m:
                    index,begin,block = m.data
                    self.pieces[index].add_block(begin, block)
                    if self.pieces[index].complete:
                        await self.event_q.put(Event(peer_id=self.peer_id, message=CompletePiece(index=index)))

                case _ as m:
                    raise ValueError(f"unexpected message {m}")

    async def add_peer(self, host: str, port: int):
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=10
        )
        peer = Peer(host=host, port=port,_reader=reader, _writer=writer)
        await self.handle_peer(peer, outbound=True)


    async def start_server(self, port: int|None=None):
        server = await asyncio.start_server(
            lambda r,w: self.handle_peer(Peer.from_streams(r,w), outbound=False), '127.0.0.1', port
        )
        addr = server.sockets[0].getsockname()
        log.info(f'Listening on {addr}')
        async with server:
            await server.serve_forever()


    async def start(self, port: int|None=None):
        await asyncio.gather(*(self.start_server(port=port), self.handle_events()))
