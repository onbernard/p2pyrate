from typing import (
    Literal,
    Self,
)
from dataclasses import dataclass, field
from asyncio import StreamReader
import hashlib
import struct

from bencodepy.exceptions import BencodeDecodeError
import bencode2



@dataclass
class MetadataProtocolInfo:
    ut_metadata: int|None
    metadata_size: int|None


class ExtendedHandshakeMessage(dict):
    @property
    def m(self) -> dict|None:
        return self.get(b"m")
    @property
    def metadata_size(self) -> int|None:
        return self.get(b"metadata_size")
    @property
    def metadata_p(self) -> MetadataProtocolInfo:
        return MetadataProtocolInfo(
            ut_metadata=self.m.get(b"ut_metadata") if self.m else None,
            metadata_size=self.metadata_size
        )


@dataclass
class ExtendedHandshake:
    length: int
    message_id: bytes
    extended_message_id: bytes
    payload: bytes

    @property
    def message(self) -> ExtendedHandshakeMessage|None:
        try:
            return ExtendedHandshakeMessage(bencode2.bdecode(self.payload))
        except BencodeDecodeError:
            return None

    @classmethod
    def from_bytes(cls, buf: bytes) -> Self|None:
        if len(buf)<6:
            return None
        length, message_id, extended_message_id = struct.unpack("!LBB", buf[0:6])
        return cls(
            length=length,
            message_id=message_id,
            extended_message_id=extended_message_id,
            payload=buf[6:6+length-2]
        )


@dataclass
class Handshake:
    info_hash: bytes
    extensions: bytes = b"\x00"
    pstrlen: Literal[19] = 19
    pstr: Literal[b"BitTorrent protocol"] = b"BitTorrent protocol"
    peer_id: bytes = field(default_factory=lambda: b"-PC0001-" + hashlib.sha1(b"peer").digest()[:12])

    @classmethod
    def from_bytes(cls, buf: bytes) -> Self:
        assert len(buf)>=68
        pstrlen, pstr, extensions, info_hash, peer_id = struct.unpack("!B19s8s20s20s", buf[:68])
        return cls(
            pstrlen=pstrlen,
            pstr=pstr,
            extensions=extensions,
            info_hash=info_hash,
            peer_id=peer_id,
        )
    
    @classmethod
    async def from_reader(cls, reader: StreamReader) -> Self:
        buf = await reader.readexactly(68)
        return cls.from_bytes(buf)
    
    def to_bytes(self) -> bytes:
        return struct.pack(
            "!B19s8s20s20s",
            self.pstrlen,
            self.pstr,
            self.extensions,
            self.info_hash,
            self.peer_id,
        )

    @property
    def extended_support(self) -> bool:
        return int.from_bytes(self.extensions) & (1<<20) > 1
