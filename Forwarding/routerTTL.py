import sys
import socket

def parse_packet(IP_packet: bytes):
    # Ip: Primeros 4 bytes.
    # TTL: Quinto byte.
    # Puerto: Siguientes 2 bytes.
    # Mensaje: Resto del paquete.
    parsed = {
        "header": {"address": f"{IP_packet[0]}.{IP_packet[1]}.{IP_packet[2]}.{IP_packet[3]}", "a": IP_packet[0], "b": IP_packet[1], "c": IP_packet[2], "d": IP_packet[3], "puerto": int.from_bytes(IP_packet[4:6], "big"), "ttl": IP_packet[6]},
        "body": IP_packet[7:].decode(),
    }
    return parsed

def create_packet(parsed_IP_packet):
    header = parsed_IP_packet["header"]

    ip = bytes([header["a"], header["b"], header["c"], header["d"]])
    puerto = header["puerto"].to_bytes(2, "big")
    body = parsed_IP_packet["body"].encode()
    ttl = bytes([header["ttl"]]) 

    return ip + puerto + ttl + body

ultimo_indice_por_area: dict[tuple[str, tuple[tuple[str, int], ...]], int] = {}

def check_routes(routes_file_name: str, destination_address: tuple[str, int]) -> tuple[str, int]:
    target_port = destination_address[1]
    candidatas: list[tuple[str, int]] = []

    with open(routes_file_name, "r") as f:
        for line in f:
            partes = line.split()
            if len(partes) < 5:
                continue  # línea vacía o mal formada

            puerto_inicio = int(partes[1])
            puerto_fin = int(partes[2])

            if puerto_inicio <= target_port <= puerto_fin:
                candidatas.append((partes[3], int(partes[4])))

    if not candidatas:
        return None

    # El "área" queda definida por quiénes son las candidatas para este puerto.
    clave = (routes_file_name, tuple(candidatas))
    indice = ultimo_indice_por_area.get(clave, 0) % len(candidatas)
    ultimo_indice_por_area[clave] = (indice + 1) % len(candidatas)

    return candidatas[indice]

IP_PACKET_1 = bytes([192, 168, 1, 100]) + (5000).to_bytes(2, "big") + (10).to_bytes(1, "big") + b"Hola, este es un mensaje de prueba."
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

    while True:
        data, addr = router.recvfrom(1024)

        parsed = parse_packet(data)

        if parsed["header"]["ttl"] == 0:
            print(f"Se recibió paquete {parsed['header']['address']} con TTL 0.")
            continue

        if parsed["header"]["puerto"] == puerto:
            print(parsed["body"])
        
        else:
            hop = check_routes(rutas, (f"{parsed['header']['address']}", parsed["header"]["puerto"]))
            if hop is None:
                print(f"No hay rutas hacia {parsed['header']['address']}:{parsed['header']['puerto']} para paquete {parsed["header"]["address"]}:{parsed["header"]["puerto"]}")

            else:
                parsed["header"]["ttl"] -= 1
                print(f"Redirigiendo paquete {parsed['header']['address']}:{parsed['header']['puerto']} con destino final {parsed['header']['address']}:{parsed['header']['puerto']} desde {address} hacia {hop[0]}:{hop[1]}")
                router.sendto(create_packet(parsed), hop)
