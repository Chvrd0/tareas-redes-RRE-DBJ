import socket
from dnslib import DNSRecord
from dnslib.dns import QTYPE, A
import dnslib

IP_VM = "localhost"
ROOT = "198.41.0.4"
DEBUG = True

# Estructuras para el caché
query_history = []
dns_cache = {}


def parseDNS(data):
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
    req = DNSRecord.parse(mensaje_consulta)
    qname = str(req.get_q().get_qname())

    if DEBUG:
        print(f"(debug) Consultando '{qname}' a '{ns_name}' con dirección IP '{ip_addr}'")

    dns_server_addr = (ip_addr, 53)
    dns_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    dns_socket.sendto(mensaje_consulta, dns_server_addr)
    data, _ = dns_socket.recvfrom(4096)
    dns_socket.close()

    if not data:
        return b""

    ans = parseDNS(data)

    # b.- Revisar si existe una respuesta A
    if ans["ANCOUNT"] != 0:
        for i in ans["ANSWER"]:
            if QTYPE.get(i.rtype) == "A":
                return data

    # c.- Buscar una delegación a un Name Server
    ns = ""

    for i in ans["AUTHORITY"]:
        if QTYPE.get(i.rtype) == "NS":
            ns = str(i.rdata)
            break

    if ns:
        # c.i.- Buscar la IP del Name Server en Additional
        for j in ans["ADDITIONAL"]:
            if QTYPE.get(j.rtype) == "A" and str(j.rname) == ns:
                return resolver(mensaje_consulta, str(j.rdata), ns)

        # c.ii.- Si no hay IP en Additional, resolver el Name Server
        q = DNSRecord.question(ns)
        ns_response = resolver(bytes(q.pack()))

        if ns_response:
            ns_ans = parseDNS(ns_response)

            for rr in ns_ans["ANSWER"]:
                if QTYPE.get(rr.rtype) == "A":
                    return resolver(
                        mensaje_consulta,
                        str(rr.rdata),
                        ns
                    )

    # d.- Otro tipo de respuesta
    return b""


if __name__ == "__main__":
    buff_size = 10000
    address = (IP_VM, 8000)

    print(f"Creando socket - Servidor DNS en {address[0]}:{address[1]}")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(address)

    while True:
        msg, remitente = server_socket.recvfrom(buff_size)

        req = DNSRecord.parse(msg)
        qname = str(req.get_q().get_qname())

        # 1. Guardar las últimas 20 consultas
        query_history.append(qname)

        if len(query_history) > 20:
            query_history.pop(0)

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

        # 3. Revisar el caché
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

        # 4. Resolver la consulta
        response_bytes = resolver(msg)

        if response_bytes:
            server_socket.sendto(response_bytes, remitente)

            # 5. Guardar la IP obtenida en el caché
            res_parsed = parseDNS(response_bytes)

            for rr in res_parsed["ANSWER"]:
                if QTYPE.get(rr.rtype) == "A":
                    dns_cache[qname] = str(rr.rdata)
                    break
        else:
            if DEBUG:
                print(f"(debug) No se pudo resolver la consulta para {qname}")

