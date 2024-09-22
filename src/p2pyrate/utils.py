
def bl_to_bitfield(boolean_list: list[bool]) -> bytes:
    lcopy = boolean_list.copy()
    if len(lcopy) % 8 != 0:
        lcopy += [False] * (8-len(lcopy)%8) # Pad
    return sum(int(b)*(2**i) for i,b in enumerate(reversed(lcopy))).to_bytes(length=len(lcopy)//8)

def bitfield_to_bl(bitfield: bytes) -> list[bool]:
    outp = []
    for b in bitfield:
        for i in range(8):
            offset = 7-i
            outp.append(b & (1 << offset) >0)
    return outp