"""Emisor de datagramas IP para la actividad de fragmentación.

Construye un único paquete IP (offset 0, flag 0, con el ID y TTL indicados) a
partir del contenido del archivo ``msg.txt`` y lo inyecta en un router de
entrada. El router se encargará de fragmentarlo según el MTU de cada enlace.

Uso:
    python3 msg_sender.py <IP_dest>:<Puerto_dest>:<TTL>:<ID> <IP_router> <Puerto_router>

Ejemplo:
    python3 msg_sender.py 127.0.0.1:8885:10:347 127.0.0.1 8881
"""

import socket
import sys

from router import create_packet

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "Uso: python3 msg_sender.py <IP_dest>:<Puerto_dest>:<TTL>:<ID> "
            "<IP_router> <Puerto_router>"
        )
        sys.exit(1)

    campos = sys.argv[1].split(":")
    ip_dest = campos[0]
    puerto_dest = int(campos[1])
    ttl = int(campos[2])
    pid = int(campos[3])

    ip_router = sys.argv[2]
    puerto_router = int(sys.argv[3])

    # El mensaje a enviar se lee en bytes desde msg.txt (datagrama único).
    with open("msg.txt", "rb") as f:
        message = f.read()

    a, b, c, d = [int(x) for x in ip_dest.split(".")]
    parsed = {
        "header": {
            "a": a, "b": b, "c": c, "d": d,
            "puerto": puerto_dest,
            "ttl": ttl,
            "id": pid,
            "offset": 0,
            "tamano": len(message),
            "flag": 0,
        },
        "body": message,
    }
    packet = create_packet(parsed)

    socket_sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    socket_sender.sendto(packet, (ip_router, puerto_router))
    print(
        f"Enviado paquete ID={pid} dest {ip_dest}:{puerto_dest} TTL={ttl} "
        f"mensaje={len(message)} bytes (total {len(packet)} bytes) hacia "
        f"{ip_router}:{puerto_router}"
    )
