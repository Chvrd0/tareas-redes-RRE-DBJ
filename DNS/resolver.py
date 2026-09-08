"""
Documentación Técnica: Resolver DNS Iterativo

Este script implementa un servidor de resolución de nombres de dominio (DNS) 
iterativo utilizando sockets UDP y la librería dnslib. El sistema consulta a 
los servidores raíz y sigue las delegaciones hasta encontrar la dirección IP 
solicitada, incorporando un sistema de caché dinámico basado en la frecuencia 
de las consultas.
"""

import socket
from dnslib import DNSRecord
from dnslib.dns import QTYPE, A
import dnslib

# --- 1. Parámetros de Configuración Global ---
IP_VM = "localhost"  # Dirección IP local o de la máquina virtual (Escucha del servidor)
ROOT = "198.41.0.4"  # IP del servidor DNS raíz para iniciar las búsquedas recursivas
DEBUG = True         # Activa la impresión de la traza de consultas en consola

# --- 2. Estructuras de Caché ---
query_history = []   # Almacena las últimas 20 consultas recibidas
dns_cache = {}       # Asocia dominios (QNAME) con sus IPs resueltas


def parseDNS(data):
    """
    Toma los bytes de un mensaje DNS sin procesar y utiliza DNSRecord.parse() 
    para estructurar la información.
    
    Retorna un diccionario con:
    - QNAME: Nombre de dominio consultado.
    - ANCOUNT, NSCOUNT, ARCOUNT: Cantidades de registros en las secciones.
    - ANSWER, AUTHORITY, ADDITIONAL: Objetos con los registros (RR) de cada sección.
    """
    d = DNSRecord.parse(data)

    parsed = {
        "QNAME": str(d.get_q().get_qname()),
        "ANCOUNT": d.header.a,
        "NSCOUNT": d.header.auth,
        "ARCOUNT": d.header.ar,
        "ANSWER": d.rr,
        "AUTHORITY": d.auth,
        "ADDITIONAL": d.ar
    }

    return parsed


def resolver(mensaje_consulta: bytes, ip_addr=ROOT, ns_name=".") -> bytes:
    """
    Función recursiva central que implementa la lógica de búsqueda DNS.
    
    Flujo:
    1. Envía la petición a la IP indicada (ip_addr).
    2. Si hay respuesta 'A', retorna los bytes.
    3. Si hay delegación ('NS'), busca la IP en la sección Additional (Glue Record).
    4. Si no hay IP en Additional, pausa la búsqueda, resuelve el Name Server 
       recursivamente, y luego retoma la consulta original.
    """
    req = DNSRecord.parse(mensaje_consulta)
    qname = str(req.get_q().get_qname())

    if DEBUG:
        print(f"(debug) Consultando '{qname}' a '{ns_name}' con dirección IP '{ip_addr}'")

    dns_server_addr = (ip_addr, 53)
    dns_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # 1. Envío de Petición
    dns_socket.sendto(mensaje_consulta, dns_server_addr)
    data, _ = dns_socket.recvfrom(4096)
    dns_socket.close()

    if not data:
        return b""

    ans = parseDNS(data)

    # 2. Condición de Éxito: Revisar si existe una respuesta A
    if ans["ANCOUNT"] != 0:
        for i in ans["ANSWER"]:
            if QTYPE.get(i.rtype) == "A":
                return data

    # 3. Manejo de Delegaciones: Buscar delegación a un Name Server
    ns = ""
    for i in ans["AUTHORITY"]:
        if QTYPE.get(i.rtype) == "NS":
            ns = str(i.rdata)
            break

    if ns:
        # 4. Búsqueda en Additional (Glue Record)
        for j in ans["ADDITIONAL"]:
            if QTYPE.get(j.rtype) == "A" and str(j.rname) == ns:
                return resolver(mensaje_consulta, str(j.rdata), ns)

        # 5. Resolución de Name Server sin Glue Record
        q = DNSRecord.question(ns)
        ns_response = resolver(bytes(q.pack()))

        if ns_response:
            ns_ans = parseDNS(ns_response)

            for rr in ns_ans["ANSWER"]:
                if QTYPE.get(rr.rtype) == "A":
                    # Retomamos la consulta original usando la IP recién encontrada
                    return resolver(
                        mensaje_consulta,
                        str(rr.rdata),
                        ns
                    )

    # 6. Descarte: Otro tipo de respuesta
    return b""


if __name__ == "__main__":
    buff_size = 10000
    address = (IP_VM, 8000)

    print(f"Creando socket - Servidor DNS en {address[0]}:{address[1]}")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(address)

    # Ciclo infinito de escucha del servidor
    while True:
        msg, remitente = server_socket.recvfrom(buff_size)

        req = DNSRecord.parse(msg)
        qname = str(req.get_q().get_qname())

        # --- ACTUALIZACIÓN DE HISTORIAL ---
        # 1. Guardar las últimas 20 consultas
        query_history.append(qname)
        if len(query_history) > 20:
            query_history.pop(0)

        # --- CÁLCULO DE FRECUENCIA ---
        # 2. Calcular los 3 dominios más consultados
        frecuencias = {}
        for dominio in query_history:
            if dominio in frecuencias:
                frecuencias[dominio] += 1
            else:
                frecuencias[dominio] = 1

        dominios_ordenados = sorted(
            frecuencias.items(),
            key=lambda x: x[1],
            reverse=True
        )
        top_3 = [item[0] for item in dominios_ordenados[:3]]

        # --- INYECCIÓN DESDE CACHÉ ---
        # 3. Revisar el caché y armar respuesta si cumple los requisitos
        if qname in top_3 and qname in dns_cache:
            if DEBUG:
                print(f"(debug) RESPONDIENDO DESDE CACHE: {qname} -> {dns_cache[qname]}")

            reply = req.reply()
            reply.add_answer(
                dnslib.dns.RR(
                    qname,
                    QTYPE.A,
                    rdata=A(dns_cache[qname])
                )
            )

            server_socket.sendto(reply.pack(), remitente)
            continue

        # --- RESOLUCIÓN EXTERNA ---
        # 4. Si no está en caché o no es top 3, resolver la consulta hacia internet
        response_bytes = resolver(msg)

        if response_bytes:
            server_socket.sendto(response_bytes, remitente)

            # --- ALMACENAMIENTO DE RESULTADOS ---
            # 5. Guardar la IP obtenida en el caché para futuras consultas
            res_parsed = parseDNS(response_bytes)

            for rr in res_parsed["ANSWER"]:
                if QTYPE.get(rr.rtype) == "A":
                    dns_cache[qname] = str(rr.rdata)
                    break
        else:
            if DEBUG:
                print(f"(debug) No se pudo resolver la consulta para {qname}")