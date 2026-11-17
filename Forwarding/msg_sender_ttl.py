"""Cliente emisor por lotes de paquetes UDP con soporte de TTL.

Este módulo lee mensajes línea por línea desde un archivo de texto local
(``msg.txt``), construye datagramas con la cabecera personalizada de 7 bytes
(IPv4 + Puerto de destino + TTL) y los envía a un router de inicio para su
enrutamiento hacia el destino final.

Nota de compatibilidad:
    El formato de paquete generado (con el séptimo byte reservado para el TTL)
    es compatible con la implementación ``routerTTL.py``.

Uso desde terminal:
    python3 msg_sender_ttl.py <IP_Destino>:<Puerto_Destino>:<TTL> <IP_Router> <Puerto_Router>

Ejemplo:
    python3 msg_sender_ttl.py 127.0.0.1:8000:10 127.0.0.1 7000
"""

import socket
import sys

if __name__ == "__main__":
    # Validación de argumentos de línea de comandos
    if len(sys.argv) != 4:
        print(
            "Uso: python3 msg_sender_ttl.py <IP_Destino>:<Puerto_Destino>:<TTL> <IP_Router> <Puerto_Router>"
        )
        sys.exit(1)

    # Dirección y puerto local desde donde el emisor transmitirá los datagramas
    address = ("localhost", 5000)

    # Inicialización del socket UDP (AF_INET = IPv4, SOCK_DGRAM = UDP)
    socket_sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    socket_sender.bind(address)

    # Extracción de los campos de cabecera desde el primer argumento (<IP>:<Puerto>:<TTL>):
    # - headers[0]: Dirección IPv4 de destino final.
    # - headers[1]: Puerto de destino final.
    # - headers[2]: Valor inicial de Time To Live (saltos máximos permitidos).
    headers = sys.argv[1].split(":")

    # Dirección y puerto del primer salto (router de entrada que recibirá los paquetes)
    ip_envio = sys.argv[2]
    puerto_envio = int(sys.argv[3])

    # Archivo fuente que contiene un mensaje por línea a transmitir
    archivo = "msg.txt"

    with open(archivo, "r") as f:
        for line in f:
            # Serialización del paquete (cabecera de 7 bytes + cuerpo en UTF-8):
            # - Bytes [0:4]: Octetos de la IPv4 de destino final.
            # - Bytes [4:6]: Puerto de destino final en formato Big-Endian.
            # - Byte  [6]:   Valor inicial de TTL en 1 byte sin signo.
            # - Bytes [7:]:  Línea leída del archivo codificada en bytes.
            packet = (
                bytes([int(octeto) for octeto in headers[0].split(".")])
                + int(headers[1]).to_bytes(2, "big")
                + int(headers[2]).to_bytes(1, "big")
                + line.encode()
            )

            # Inyecta el datagrama en el router inicial especificado
            socket_sender.sendto(packet, (ip_envio, puerto_envio))