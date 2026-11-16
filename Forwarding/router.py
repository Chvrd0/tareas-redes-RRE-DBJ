import sys
import socket

def parse_packet(IP_packet: bytes):
    # Ip: Primeros 4 bytes.
    # Puerto: Siguientes 2 bytes.
    # Mensaje: Resto del paquete.
    parsed = {
        "header": {"a": IP_packet[0], "b": IP_packet[1], "c": IP_packet[2], "d": IP_packet[3], "puerto": int.from_bytes(IP_packet[4:6], "big")},
        "body": IP_packet[6:].decode(),
    }
    return parsed



if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python3 router.py <IP> <Puerto> <Rutas>")
        sys.exit(1)

    ip = sys.argv[1]
    puerto = int(sys.argv[2])
    address = (ip, puerto)

    router = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    router.bind(address)

    rutas = sys.argv[3]
    print(f"Router iniciado en {ip}:{puerto} con rutas: {rutas}")

    

    while True:
        data, addr = router.recvfrom(1024)
        print(f"Mensaje recibido de {addr}: {data.decode()}")
