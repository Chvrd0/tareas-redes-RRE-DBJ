"""Cliente emisor de paquetes UDP para pruebas de enrutamiento.

Este módulo implementa un cliente interactivo por consola que construye
paquetes con la cabecera personalizada de 6 bytes (IPv4 + Puerto de destino)
y los inyecta en un router inicial para que sean enrutados hacia su destino
final.

Nota de compatibilidad:
    El formato de paquete generado (sin byte de TTL) es compatible con la
    implementación base ``router.py``.

Uso desde terminal:
    python3 msg_sender.py
"""

import socket

# Dirección y puerto local desde donde el emisor enviará los datagramas
address = ("localhost", 5000)

# Inicialización del socket UDP (AF_INET = IPv4, SOCK_DGRAM = UDP)
socket_sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
socket_sender.bind(address)

# Bucle interactivo para el envío continuo de mensajes
while True:
    # 1. Definición del destino final (se codificará dentro de la cabecera del paquete)
    ip_destino = "127.0.0.1"
    puerto_destino = int(input("Ingrese el puerto de destino: "))

    # 2. Definición del primer salto / router de inicio (destino físico del datagrama UDP)
    ip_envio = "127.0.0.1"
    puerto_envio = int(input("Ingrese el puerto de envío: "))

    # 3. Lectura de la carga útil (payload)
    msg = input("Ingrese el mensaje a enviar: ")

    # Serialización del paquete (cabecera de 6 bytes + cuerpo en UTF-8):
    # - Bytes [0:4]: Octetos de la IPv4 de destino final.
    # - Bytes [4:6]: Puerto de destino final en formato Big-Endian.
    # - Bytes [6:]:  Mensaje codificado en bytes.
    packet = (
        bytes([int(octeto) for octeto in ip_destino.split(".")])
        + puerto_destino.to_bytes(2, "big")
        + msg.encode()
    )

    # Envía el paquete al router de inicio especificado para iniciar el enrutamiento
    socket_sender.sendto(packet, (ip_envio, puerto_envio))