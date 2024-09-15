from typing import (
    Literal,
    Self,
)
from dataclasses import dataclass, field
import hashlib
import struct

from bencodepy.exceptions import BencodeDecodeError
import bencodepy


@dataclass
class ExtendedHandshake:
    length: int
    message_id: bytes
    extended_message_id: bytes
    payload: bytes

    @property
    def message(self) -> dict|None:
        try:
            return bencodepy.decode(self.payload)
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
    extensions: bytes
    info_hash: bytes
    pstrlen: Literal[19] = 19
    pstr: Literal[b"BitTorrent protocol"] = b"BitTorrent protocol"
    peer_id: bytes = field(default_factory=lambda: b"-PC0001-" + hashlib.sha1(b"peer").digest()[:12])
    extended_handshake: ExtendedHandshake|None = None

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
            extended_handshake=ExtendedHandshake.from_bytes(buf[68:])
        )
    
    def to_bytes(self) -> bytes:
        return struct.pack(
            "!B19s8s20s20s",
            self.pstrlen,
            self.pstr,
            self.extensions,
            self.info_hash,
            self.peer_id,
        )
