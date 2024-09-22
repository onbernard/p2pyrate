from typing import (
    DefaultDict,
)
from collections import defaultdict
import os

from scapy.all import rdpcap, TCP, Raw, IP # type: ignore

from p2pyrate.peer.handshake import (
    Handshake,
    ExtendedHandshake,
)


def extract_bt_handshakes(pcap: str|os.PathLike) -> dict[tuple[str,str],tuple[Handshake,ExtendedHandshake|None]]:
    packets = rdpcap(pcap)
    handshakes: dict[tuple[str,str],bytes] = {}
    # Filter normal handshakes
    for pkt in packets:
        if pkt.haslayer(TCP) and b'\x13BitTorrent protocol' in bytes(pkt[TCP].payload):
            handshakes[(pkt[IP].src,pkt[IP].dst)] = pkt[Raw].load
    # Filter extended handshakes
    ext_handshakes: dict[tuple[str,str],bytes] = {}
    for pkt in packets:
        if pkt.haslayer(TCP) and pkt.haslayer(Raw):
            raw = pkt[Raw].load
            if len(raw)>5 and raw[4]==20:
                ext_handshakes[(pkt[IP].src,pkt[IP].dst)] = raw
    # Link normal and extended handshakes
    outp: dict[tuple[str,str],tuple[Handshake,ExtendedHandshake|None]] = {}
    for session, raw in handshakes.items():
        if (hs := Handshake.from_bytes(raw)).extended_support:
            if (e_raw := ext_handshakes.get(session)) is not None:
                outp[session] = (hs, ExtendedHandshake.from_bytes(e_raw))
            else:
                outp[session] = (hs,None)
    return outp


def extract_bt_sessions(pcap: str|os.PathLike) -> list[list[tuple[bytes,float]]]:
    packets = rdpcap(str(pcap))
    sessions: DefaultDict[tuple[str,str],list[tuple[bytes,float]]] = defaultdict(list)
    for pkt in packets:
        if pkt.haslayer(TCP) and pkt.haslayer(Raw):
            sessions[(pkt[IP].src,pkt[IP].dst)].append((pkt[Raw].load,pkt.time))
    return [sorted(s, key=lambda x: x[1]) for s in sessions.values() if any(b"\x13BitTorrent protocol" in m for m,_ in s)]
