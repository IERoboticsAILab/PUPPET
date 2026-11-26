"""Ask Motive (NatNet server) for its asset definitions and print each rigid body's marker offsets.

Usage: python3 natnet_modeldef.py <server_ip>
"""
import socket
import struct
import sys

SERVER = sys.argv[1] if len(sys.argv) > 1 else "10.205.3.3"
CMD_PORT = 1510
NAT_CONNECT, NAT_SERVERINFO, NAT_REQUEST_MODELDEF, NAT_MODELDEF = 0, 1, 4, 5

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("", 0))
s.settimeout(3)


def request(msg_id, payload=b""):
    s.sendto(struct.pack("<HH", msg_id, len(payload)) + payload, (SERVER, CMD_PORT))
    while True:
        data, _ = s.recvfrom(65535 * 4)
        mid, n = struct.unpack_from("<HH", data)
        if mid in (NAT_SERVERINFO, NAT_MODELDEF):
            return mid, data[4:]


# Connect: payload is a 256-byte app name + version info; zeros are accepted.
mid, info = request(NAT_CONNECT, b"\0" * 270)
name = info[:256].split(b"\0")[0].decode()
app_ver = tuple(info[256:260])
natnet_ver = tuple(info[260:264])
print(f"server: {name} app {app_ver} natnet {natnet_ver}")

mid, d = request(NAT_REQUEST_MODELDEF)
major, minor = natnet_ver[0], natnet_ver[1]
sized = (major, minor) >= (4, 1)


def cstr(buf, off):
    end = buf.index(b"\0", off)
    return buf[off:end].decode(errors="replace"), end + 1


off = 0
(n,) = struct.unpack_from("<i", d, off); off += 4
for _ in range(n):
    (typ,) = struct.unpack_from("<i", d, off); off += 4
    size = None
    if sized:
        (size,) = struct.unpack_from("<i", d, off); off += 4
    start = off
    if typ == 1:  # rigid body
        rb, off = cstr(d, off)
        rid, parent = struct.unpack_from("<ii", d, off); off += 8
        px, py, pz = struct.unpack_from("<fff", d, off); off += 12
        off += 16  # rotation quaternion (present in the NatNet 4.5 stream from Motive 3.5)
        (nm,) = struct.unpack_from("<i", d, off); off += 4
        pts = [struct.unpack_from("<fff", d, off + 12 * i) for i in range(nm)]
        print(f"\nRIGID BODY '{rb}' id={rid} parent={parent} nMarkers={nm}")
        for i, p in enumerate(pts):
            print(f"  marker {i}: x={p[0]*1000:8.1f}  y={p[1]*1000:8.1f}  z={p[2]*1000:8.1f} mm")
    else:
        if size is None:
            print(f"type {typ} without size info; stopping")
            break
    if size is not None:
        off = start + size
