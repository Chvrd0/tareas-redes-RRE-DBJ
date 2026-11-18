"""Router con fragmentación y re-ensamblado de datagramas IP sobre UDP.

Construido sobre el router de la actividad de forwarding. Cada enlace tiene un
MTU (Maximum Transmission Unit) indicado en la tabla de rutas. Antes de hacer
forward, el router fragmenta el paquete según el MTU del enlace de salida, y
cuando un paquete (o sus fragmentos) llega a su destino, el router los almacena
por ID e intenta re-ensamblar el datagrama original.

Estructura del header IP (16 bytes fijos):
    - Bytes [0:4]   Dirección IPv4 de destino (4 octetos a.b.c.d).
    - Bytes [4:6]   Puerto de destino (2 bytes, big-endian).
    - Byte  [6]     TTL (1 byte sin signo).
    - Bytes [7:9]   ID del datagrama (2 bytes, big-endian).
    - Bytes [9:11]  Offset en bytes dentro del mensaje original (2 bytes).
    - Bytes [11:15] Tamaño del mensaje de este fragmento, sin header (4 bytes).
    - Byte  [15]    FLAG More-Fragment: 1 si quedan más fragmentos, 0 si es el último.
    - Bytes [16:]   Mensaje (payload) en bytes.

Uso:
    python3 router.py <IP> <Puerto> <Archivo_Rutas>
"""

import sys
import socket

# Tamaño fijo del header IP en bytes.
HEADER_SIZE = 16


def parse_packet(IP_packet: bytes) -> dict:
    """Deserializa un paquete en bytes a un diccionario con header y body.

    Args:
        IP_packet (bytes): datagrama recibido por el socket.

    Returns:
        dict: con ``"header"`` (address, a, b, c, d, puerto, ttl, id, offset,
        tamano, flag) y ``"body"`` (payload en bytes).
    """
    tamano = int.from_bytes(IP_packet[11:15], "big")
    parsed = {
        "header": {
            "address": f"{IP_packet[0]}.{IP_packet[1]}.{IP_packet[2]}.{IP_packet[3]}",
            "a": IP_packet[0],
            "b": IP_packet[1],
            "c": IP_packet[2],
            "d": IP_packet[3],
            "puerto": int.from_bytes(IP_packet[4:6], "big"),
            "ttl": IP_packet[6],
            "id": int.from_bytes(IP_packet[7:9], "big"),
            "offset": int.from_bytes(IP_packet[9:11], "big"),
            "tamano": tamano,
            "flag": IP_packet[15],
        },
        # El payload se mantiene en bytes para poder fragmentar sin romper
        # caracteres multibyte; se decodifica solo al imprimir en destino.
        "body": IP_packet[HEADER_SIZE:HEADER_SIZE + tamano],
    }
    return parsed


def create_packet(parsed_IP_packet: dict) -> bytes:
    """Serializa un diccionario de paquete estructurado a bytes.

    Args:
        parsed_IP_packet (dict): diccionario equivalente al de :func:`parse_packet`.

    Returns:
        bytes: paquete listo para transmitir.
    """
    h = parsed_IP_packet["header"]
    header = (
        bytes([h["a"], h["b"], h["c"], h["d"]])
        + h["puerto"].to_bytes(2, "big")
        + bytes([h["ttl"]])
        + h["id"].to_bytes(2, "big")
        + h["offset"].to_bytes(2, "big")
        + h["tamano"].to_bytes(4, "big")
        + bytes([h["flag"]])
    )
    body = parsed_IP_packet["body"]
    if isinstance(body, str):
        body = body.encode()
    return header + body


# Estado global para el índice de rotación Round-Robin por conjunto de rutas.
ultimo_indice_por_area: dict = {}


def check_routes(routes_file_name: str, destination_address: tuple):
    """Consulta la tabla de rutas y retorna (siguiente_salto, MTU).

    El formato de cada línea ahora incluye el MTU del enlace:
        ``<Red> <Puerto_ini> <Puerto_fin> <IP_next> <Puerto_next> <MTU>``

    Si hay varias rutas candidatas para el destino, alterna entre ellas con
    Round-Robin. Soporta líneas sin MTU (usa un MTU grande que no fragmenta).

    Returns:
        tuple | None: ``((ip, puerto), mtu)`` del siguiente salto, o ``None``.
    """
    target_port = destination_address[1]
    candidatas = []

    with open(routes_file_name, "r") as f:
        for line in f:
            partes = line.split()
            if len(partes) < 5:
                continue  # línea vacía o mal formada

            puerto_inicio = int(partes[1])
            puerto_fin = int(partes[2])
            # MTU opcional: si la línea no lo trae, se asume "muy grande".
            mtu = int(partes[5]) if len(partes) >= 6 else 65535

            if puerto_inicio <= target_port <= puerto_fin:
                candidatas.append(((partes[3], int(partes[4])), mtu))

    if not candidatas:
        return None

    clave = (routes_file_name, tuple(candidatas))
    indice = ultimo_indice_por_area.get(clave, 0) % len(candidatas)
    ultimo_indice_por_area[clave] = (indice + 1) % len(candidatas)
    return candidatas[indice]


def fragment_IP_packet(IP_packet: bytes, MTU: int) -> list:
    """Fragmenta un datagrama IP para que cada fragmento quepa en el MTU.

    Si el tamaño completo del paquete (header + datos) es menor o igual al MTU,
    no requiere fragmentación y se retorna ``[IP_packet]``. En caso contrario se
    parte el mensaje en trozos de ``MTU - HEADER_SIZE`` bytes, re-configurando
    Offset, Tamaño y FLAG en cada fragmento. Si el paquete de entrada ya es un
    fragmento (offset o flag no triviales), los sub-fragmentos heredan su offset
    base y su flag en el último trozo (re-fragmentación).

    Returns:
        list[bytes]: lista de fragmentos (largo siempre >= 1).
    """
    if len(IP_packet) <= MTU:
        return [IP_packet]

    parsed = parse_packet(IP_packet)
    h = parsed["header"]
    message = parsed["body"]
    base_offset = h["offset"]
    parent_flag = h["flag"]

    chunk_size = MTU - HEADER_SIZE
    if chunk_size <= 0:
        # El MTU no alcanza ni para un byte de datos: no se puede fragmentar.
        raise ValueError(f"MTU {MTU} demasiado pequeño para el header de {HEADER_SIZE} bytes")

    fragments = []
    total = len(message)
    i = 0
    while i < total:
        chunk = message[i:i + chunk_size]
        es_ultimo = (i + len(chunk) >= total)
        frag_header = dict(h)
        frag_header["offset"] = base_offset + i
        frag_header["tamano"] = len(chunk)
        # El último trozo hereda el flag del paquete original; los demás = 1.
        frag_header["flag"] = parent_flag if es_ultimo else 1
        fragments.append(create_packet({"header": frag_header, "body": chunk}))
        i += chunk_size

    return fragments


def reassemble_IP_packet(fragment_list: list):
    """Re-ensambla un datagrama IP a partir de una lista de fragmentos.

    La lista puede llegar desordenada o con duplicados. Retorna el paquete IP
    completo (bytes) si la secuencia está completa y contigua, o ``None`` si
    faltan fragmentos. Una lista de un elemento con offset 0 y flag 0 es un
    paquete sin fragmentar (completo).

    Returns:
        bytes | None: paquete IP re-ensamblado, o ``None`` si está incompleto.
    """
    # Elimina duplicados quedándose con un fragmento por offset.
    por_offset = {}
    for frag in fragment_list:
        off = parse_packet(frag)["header"]["offset"]
        por_offset[off] = frag
    frags = [por_offset[o] for o in sorted(por_offset)]

    primero = parse_packet(frags[0])["header"]
    if len(frags) == 1:
        # Paquete completo sin fragmentar: offset 0 y es el último (flag 0).
        if primero["offset"] == 0 and primero["flag"] == 0:
            return frags[0]
        return None  # fragmento suelto: lista incompleta

    # Verifica contigüidad desde offset 0 y que el último presente sea el final.
    expected_offset = 0
    message = b""
    for idx, frag in enumerate(frags):
        h = parse_packet(frag)["header"]
        if h["offset"] != expected_offset:
            return None  # hay un hueco: falta un fragmento
        message += parse_packet(frag)["body"]
        expected_offset += h["tamano"]
        es_ultimo = (idx == len(frags) - 1)
        if es_ultimo and h["flag"] != 0:
            return None  # el de mayor offset no es el final: aún faltan
        if not es_ultimo and h["flag"] != 1:
            return None  # un fragmento intermedio marcado como final: inconsistente

    base = dict(parse_packet(frags[0])["header"])
    base["offset"] = 0
    base["flag"] = 0
    base["tamano"] = len(message)
    return create_packet({"header": base, "body": message})


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python3 router.py <IP> <Puerto> <Rutas>")
        sys.exit(1)

    ip = sys.argv[1]
    puerto = int(sys.argv[2])
    address = (ip, puerto)
    rutas = sys.argv[3]

    router = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    router.bind(address)
    print(f"Router iniciado en {ip}:{puerto} con rutas: {rutas}")

    # Diccionario de fragmentos recibidos PARA ESTE router, indexado por ID.
    fragmentos_por_id: dict = {}

    while True:
        data, addr = router.recvfrom(65535)
        parsed = parse_packet(data)
        h = parsed["header"]

        # 1) Descarta si el TTL se agotó.
        if h["ttl"] == 0:
            print(f"Se recibió paquete {h['address']} con TTL 0.")
            continue

        # 2) ¿El paquete es para este router? -> almacenar e intentar re-ensamblar.
        if h["puerto"] == puerto or puerto == 7000:
            fragmentos_por_id.setdefault(h["id"], []).append(data)
            packet = reassemble_IP_packet(fragmentos_por_id[h["id"]])
            if packet is not None:
                body = parse_packet(packet)["body"]
                print(body.decode(errors="replace"))
                del fragmentos_por_id[h["id"]]
            else:
                print(
                    f"Fragmento almacenado (ID={h['id']}, offset={h['offset']}, "
                    f"flag={h['flag']}): esperando más fragmentos."
                )
            continue

        # 3) Forwarding: consultar ruta + MTU.
        hop = check_routes(rutas, (h["address"], h["puerto"]))
        if hop is None:
            print(
                f"No hay rutas hacia {h['address']}:{h['puerto']} "
                f"para paquete ID={h['id']}"
            )
            continue

        next_hop, mtu = hop
        # Decrementa el TTL antes de hacer forward (se propaga a los fragmentos).
        h["ttl"] -= 1
        packet = create_packet(parsed)
        fragmentos = fragment_IP_packet(packet, mtu)
        for frag in fragmentos:
            router.sendto(frag, next_hop)
        print(
            f"Redirigiendo ID={h['id']} con destino final {h['address']}:{h['puerto']} "
            f"desde {address} hacia {next_hop[0]}:{next_hop[1]} "
            f"(MTU={mtu}, {len(fragmentos)} fragmento(s))"
        )
