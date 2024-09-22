import hashlib
import os

import bencode2


class TorrentFile(dict):
    @property
    def length(self) -> int:
        return self[b"length"]

    @property
    def path(self) -> list[bytes]:
        return self[b"path"]
    

class TorrentInfo(dict):
    @property
    def piece_length(self) -> int:
        return self[b"piece length"]
    
    @property
    def length(self) -> int|None:
        return self.get(b"length")

    @property
    def files(self) -> list[TorrentFile]:
        return [TorrentFile(_) for _ in self[b"files"]]

    @property
    def hash(self) -> bytes:
        return hashlib.sha1(bencode2.bencode(self)).digest()

    @property
    def pieces(self) -> list[bytes]:
        outp: list[bytes] = []
        dt: bytes = self[b"pieces"]
        i = 0
        pl = len(dt)
        while i<pl:
            outp.append(dt[i:min(i+20,pl)])
            i += 20
        return outp

class Metadata(dict):
    @property
    def announce(self) -> bytes:
        return self[b"announce"]

    @property
    def info(self) -> TorrentInfo:
        return TorrentInfo(self[b"info"])

    @classmethod
    def from_file(cls, fpath: str|os.PathLike):
        with open(fpath, "rb") as fp:
            data = bencode2.bdecode(fp.read())
        return cls(data)
