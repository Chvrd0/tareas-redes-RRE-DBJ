"""Simulador de enrutamiento de paquetes sobre sockets UDP.

Este módulo implementa un router básico que escucha datagramas UDP en una
dirección y puerto específicos, inspecciona la cabecera personalizada del
paquete para determinar su destino final y lo consume localmente o lo
reenvía al siguiente salto (*next hop*) aplicando balanceo de carga
Round-Robin según una tabla de enrutamiento en texto plano.

Uso desde terminal:
    python3 router.py <IP> <Puerto> <Archivo_Rutas>
"""

import sys
import socket


def parse_packet(IP_packet: bytes) -> dict:
    """Deserializa un paquete en bytes a una estructura de diccionario.

    Estructura esperada del paquete:
        - Bytes [0:4]: Dirección IPv4 de destino (4 octetos).
        - Bytes [4:6]: Puerto de destino en formato Big-Endian (2 bytes).
        - Bytes [6:]:  Carga útil (*payload*) codificada en UTF-8.

    Args:
        IP_packet (bytes): Secuencia de bytes recibida por el socket.

    Returns:
        dict: Diccionario con las claves ``"header"`` (dirección completa,
        octetos individuales ``a``, ``b``, ``c``, ``d`` y ``puerto``) y
        ``"body"`` (mensaje decodificado como ``str``).
    """
    parsed = {
        "header": {
            "address": f"{IP_packet[0]}.{IP_packet[1]}.{IP_packet[2]}.{IP_packet[3]}",
            "a": IP_packet[0],
            "b": IP_packet[1],
            "c": IP_packet[2],
            "d": IP_packet[3],
            "puerto": int.from_bytes(IP_packet[4:6], "big"),
        },
        "body": IP_packet[6:].decode(),
    }
    return parsed


def create_packet(parsed_IP_packet: dict) -> bytes:
    """Serializa un diccionario de paquete estructurado a formato de bytes.

    Args:
        parsed_IP_packet (dict): Diccionario con formato equivalente al
            retornado por :func:`parse_packet`.

    Returns:
        bytes: Paquete listo para ser transmitido a través de un socket UDP.
    """
    header = parsed_IP_packet["header"]

    ip = bytes([header["a"], header["b"], header["c"], header["d"]])
    puerto = header["puerto"].to_bytes(2, "big")
    body = parsed_IP_packet["body"].encode()

    return ip + puerto + body


# Estado global para mantener el índice de rotación (Round-Robin) por cada
# conjunto de rutas candidatas asociado a un archivo de rutas.
ultimo_indice_por_area: dict[tuple[str, tuple[tuple[str, int], ...]], int] = {}


def check_routes(
    routes_file_name: str, destination_address: tuple[str, int]
) -> tuple[str, int] | None:
    """Consulta la tabla de rutas y selecciona el siguiente salto (*next hop*).

    Lee el archivo de rutas buscando entradas cuyo rango de puertos cubra el
    puerto de destino. Si existen múltiples rutas candidatas para el mismo
    rango, alterna entre ellas de forma cíclica (Round-Robin).

    Formato esperado por línea en ``routes_file_name``:
        ``<Red/ID> <Puerto_Inicio> <Puerto_Fin> <IP_Next_Hop> <Puerto_Next_Hop>``

    Args:
        routes_file_name (str): Ruta al archivo de texto con la tabla de enrutamiento.
        destination_address (tuple[str, int]): Tupla ``(ip, puerto)`` del destino final.

    Returns:
        tuple[str, int] | None: Tupla ``(ip_salto, puerto_salto)`` del siguiente
        router al cual reenviar el paquete, o ``None`` si no existe ruta válida.
    """
    target_port = destination_address[1]
    candidatas: list[tuple[str, int]] = []

    with open(routes_file_name, "r") as f:
        for line in f:
            partes = line.split()
            if len(partes) < 5:
                continue  # Ignora líneas vacías o mal formadas

            puerto_inicio = int(partes[1])
            puerto_fin = int(partes[2])

            # Verifica si el puerto destino cae dentro del rango de la ruta
            if puerto_inicio <= target_port <= puerto_fin:
                candidatas.append((partes[3], int(partes[4])))

    if not candidatas:
        return None

    # Selección Round-Robin: la clave identifica el grupo de rutas candidatas
    clave = (routes_file_name, tuple(candidatas))
    indice = ultimo_indice_por_area.get(clave, 0) % len(candidatas)
    ultimo_indice_por_area[clave] = (indice + 1) % len(candidatas)

    return candidatas[indice]


# --- Datos de prueba para verificación de serialización/deserialización ---
IP_PACKET_1 = (
    bytes([192, 168, 1, 100])
    + (5000).to_bytes(2, "big")
    + b"Hola, este es un mensaje de prueba."
)
PARSED_PACKET_1 = parse_packet(IP_PACKET_1)
IP_PACKET_2 = create_packet(PARSED_PACKET_1)


if __name__ == "__main__":
    # Validación de argumentos de línea de comandos
    if len(sys.argv) != 4:
        print("Uso: python3 router.py <IP> <Puerto> <Rutas>")
        sys.exit(1)

    ip = sys.argv[1]
    puerto = int(sys.argv[2])
    address = (ip, puerto)
    rutas = sys.argv[3]

    # Inicialización del socket UDP (AF_INET = IPv4, SOCK_DGRAM = UDP)
    router = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    router.bind(address)
    #print("IP_packet_v1 == IP_packet_v2 ? {}".format(IP_PACKET_1 == IP_PACKET_2))
    print(f"Router iniciado en {ip}:{puerto} con rutas: {rutas}")

    # Bucle principal de recepción y reenvío de paquetes
    while True:
        data, addr = router.recvfrom(1024)
        parsed = parse_packet(data)

        # Si el puerto de destino coincide con el puerto local, el paquete llegó a su destino
        if parsed["header"]["puerto"] == puerto or puerto == 7000:
            print(parsed["body"] + "\n")
        else:
            # Busca el siguiente salto en la tabla de rutas
            destino_final = (
                f"{parsed['header']['address']}",
                parsed["header"]["puerto"],
            )
            hop = check_routes(rutas, destino_final)

            if hop is None:
                print(
                    f"No hay rutas hacia {parsed['header']['address']}:{parsed['header']['puerto']} "
                    f"para paquete {parsed['header']['address']}:{parsed['header']['puerto']}"
                )
            else:
                print(
                    f"Redirigiendo paquete {parsed['header']['address']}:{parsed['header']['puerto']} "
                    f"con destino final {parsed['header']['address']}:{parsed['header']['puerto']} "
                    f"desde {address} hacia {hop[0]}:{hop[1]}"
                )
                router.sendto(data, hop)