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

def create_packet(parsed_IP_packet):
    header = parsed_IP_packet["header"]

    ip = bytes([header["a"], header["b"], header["c"], header["d"]])
    puerto = header["puerto"].to_bytes(2, "big")
    body = parsed_IP_packet["body"].encode()

    return ip + puerto + body

def check_routes(routes_file_name: str, destination_address: tuple[str, int])-> tuple[str, int]:
    with open(routes_file_name, "r") as f:
        for line in f:
            partes = line.split(" ")
            target_port = destination_address[1]
            puerto_inicio = int(partes[1])
            puerto_fin = int(partes[2])
            if puerto_inicio <= target_port <= puerto_fin:
                return (partes[3], partes[4])
    return None

IP_PACKET_1 = bytes([192, 168, 1, 100]) + (5000).to_bytes(2, "big") + b"Hola, este es un mensaje de prueba."
PARSED_PACKET_1 = parse_packet(IP_PACKET_1)
IP_PACKET_2 = create_packet(PARSED_PACKET_1)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python3 router.py <IP> <Puerto> <Rutas>")
        sys.exit(1)

    ip = sys.argv[1]
    puerto = int(sys.argv[2])
    address = (ip, puerto)

    router = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    router.bind(address)
    print("IP_packet_v1 == IP_packet_v2 ? {}".format(IP_PACKET_1 == IP_PACKET_2))

    rutas = sys.argv[3]
    print(f"Router iniciado en {ip}:{puerto} con rutas: {rutas}")

    print(check_routes(rutas, ("192.168.1.100", 8882)))

    while True:
        data, addr = router.recvfrom(1024)

        parsed = parse_packet(data)
        print(f"Paquete parseado: {parsed}")

