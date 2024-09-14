from dataclasses import dataclass
from urllib.parse import urlparse
import asyncio
import socket
import struct
import random
import binascii

import async_timeout
import asyncudp


def make_connection_request(transaction_id: int|None=None) -> tuple[int,bytes]:
    if transaction_id is None:
        transaction_id = random.randint(0, 0xFFFFFFFF)
    assert 0<transaction_id<0xFFFFFFFF
    return transaction_id, struct.pack(
        "!QII",
        0x41727101980,  # 64-bit connection id
        0,              # 32-bit integer action
        transaction_id, # 32-bit integer transaction_id
    )

@dataclass
class ConnectionResponse:
    action: int
    transaction_id: int
    connection_id: int

def parse_connection_response(buf: bytes) -> ConnectionResponse:
    if len(buf)<16:
        raise ValueError(f"connection response too short {len(buf)}<16")
    action, transaction_id, connection_id = struct.unpack(
        "!IIQ",
        buf
    )
    return ConnectionResponse(action, transaction_id, connection_id)


@dataclass
class AnnounceParams:
    connection_id: int
    info_hash: str
    peer_id: str|None = None
    transaction_id: int|None = None
    address: int|None = None
    port: int|None = None
    key: int|None = None


def make_announce_request(p: AnnounceParams):
    if p.transaction_id is None:
        p.transaction_id = random.randint(0,0xFFFFFFFF)
    if p.peer_id is None:
        p.peer_id = "".join(str(random.randint(0,9)) for _ in range(40))
    if p.address is None:
        p.address = 0
    if p.port is None:
        p.port = random.randint(1024,65535)
    if p.key is None:
        p.key = random.randint(0, 0xFFFFFFFF)
    return struct.pack(
        "!QII20s20sQqQIIIiH",
        p.connection_id,                # 64-bit connection ID
        0x1,                            # 32-bit action
        p.transaction_id,               # 32-bit transaction ID
        binascii.a2b_hex(p.info_hash),  # 20-bytes info_hash
        binascii.a2b_hex(p.peer_id),    # 20-bytes peer_id
        0x0,                            # 64-bit integer downloaded
        -1,                             # 64-bit left
        0x0,                            # 64-bit uploaded
        0x2,                            # 32-bit event (started = 2),
        p.address,                      # 32-bit ip address (optional)
        p.key,                          # 32-bit key (optional)
        -1,                             # 32-bit numwant
        p.port,                         # 16-bit port
    )


@dataclass
class AnnounceResponse:
    action: int
    transaction_id: int
    interval: int
    leechers: int
    seeders: int
    peers: list[tuple[str,int]]


def parse_announce_reponse(buf: bytes):
    if len(buf)<20:
        raise ValueError(f"announce response too short {len(buf)}<20")
    action, transaction_id, interval, leechers, seeders = struct.unpack("!IIIII", buf[0:20])
    n_peers = (len(buf) - 20) // 6
    peer_data = buf[20:]
    peers: list[tuple[str,int]] = []
    for i in range(0, n_peers):
        ip = socket.inet_ntoa(peer_data[i:i+4])
        port = struct.unpack("!H", peer_data[i*6+4:i*6+6])[0]
        peers.append((ip,port))
    return AnnounceResponse(
        action=action,
        transaction_id=transaction_id,
        interval=interval,
        leechers=leechers,
        seeders=seeders,
        peers=peers
    )


async def request_peers(info_hash: str, tracker_url: str, timeout: int=10) -> list[tuple[str,int]]:
    # RESOLVE TRACKER IP
    tracker = urlparse(tracker_url)
    assert tracker.scheme=="udp"
    loop = asyncio.get_running_loop()
    tracker_addr = await loop.getaddrinfo(
        host=tracker.hostname,
        port=tracker.port,
        family=socket.AF_INET,
        type=socket.SOCK_DGRAM,
    )
    tracker_ip = tracker_addr[0][4]
    sock = await asyncudp.create_socket(remote_addr=tracker_ip)
    # MAKE CONNECTION REQUEST
    transaction_id, buf = make_connection_request()
    sock.sendto(buf)
    async with async_timeout.timeout(timeout):
        buf, _ = await sock.recvfrom()
    connection_response = parse_connection_response(buf)
    assert connection_response.action == 0
    assert connection_response.transaction_id==transaction_id
    # MAKE ANNOUNCE REQUEST
    announce_params = AnnounceParams(
        connection_response.connection_id,
        info_hash=info_hash
    )
    sock.sendto(make_announce_request(announce_params))
    async with async_timeout.timeout(timeout):
        buf, _ = await sock.recvfrom()
    announce_response = parse_announce_reponse(buf)
    assert announce_response.action==1
    return announce_response.peers
    