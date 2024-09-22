from typing import (
    Self,
)
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs


@dataclass
class Magnet:
    xt: str
    tr: list[str]

    @classmethod
    def from_url(cls, url: str) -> Self:
        magnet = urlparse(url)
        queries = parse_qs(magnet.query)
        xt = queries["xt"][0].split(":")[-1]
        tr = queries["tr"]
        return cls(
            xt=xt,
            tr=tr,
        )