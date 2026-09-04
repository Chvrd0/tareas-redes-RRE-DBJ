import socket
from dnslib import DNSRecord
from dnslib.dns import CLASS, QTYPE, A
import dnslib 
IP_VM = "localhost"
ROOT = "198.41.0.4"
DEBUG = True


def parseDNS(data):
    d = DNSRecord.parse(data)

    parsed = {
        "QNAME": d.get_q().get_qname(),
        "ANCOUNT": d.header.a,
        "NSCOUNT": d.header.auth,
        "ARCOUNT": d.header.ar,
        "ANSWER": d.rr,
        "AUTHORITY": d.auth,
        "ADDITIONAL": d.ar
    }
    return parsed


def resolver(mensaje_consulta: bytes , ip_addr = ROOT) -> bytes:
    if DEBUG: print("\n---- FUNCIÓN DE RESOLVER ----")

    dns_server_addr = (ip_addr, 53)
    dns_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dns_socket.sendto(mensaje_consulta, dns_server_addr)

    data, _ = dns_socket.recvfrom(4096)
    ans = parseDNS(data)

    if ans["ANCOUNT"] != 0:
        if DEBUG: print("Respuestas existentes. Analizando respuestas...")
        for i in ans["ANSWER"]:
            if QTYPE.get(i.rtype) == "A":
                if DEBUG: print(f"Se resolvió exitosamente: \n{str(ans["QNAME"])} -> {str(i.rdata)}\n ")
                return data

    ns, nsb = "", False
    for i in ans["AUTHORITY"]:
        if QTYPE.get(i.rtype) == "NS":
            nsb = True
            ns = str(i.rdata)
            if DEBUG: print(f"Se encontró una delegación a Name Server. Delegando... \n{str(ans['QNAME'])} -> {ns}")
            break

    if nsb:
        for j in ans["ADDITIONAL"]:
            if QTYPE.get(j.rtype) == "A":
                if DEBUG: print(f"Se encontró una IP para la delegación. Resolviendo... \n{str(ans['QNAME'])} -> {j.rdata}")
                return resolver(mensaje_consulta, str(j.rdata))

        if DEBUG: print(f"No se encontró IP para la delegación. Resolviendo para el name server...\n{ns}")
        q = DNSRecord.question(ns)
        qa = parseDNS(resolver(bytes(q.pack())))

        if DEBUG: print(f"Name Server resuelto. Delegando a la IP encontrada... \n{str(ans['QNAME'])} -> {str(qa["ANSWER"][0].rdata)}")
        return resolver(mensaje_consulta, str(qa["ANSWER"][0].rdata))


    





if __name__ == "__main__":
    buff_size = 10000
    address = (IP_VM, 8000)

    print('Creando socket - Servidor')

    server_socket =  socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(address)

    while True:
        msg, remitente = server_socket.recvfrom(buff_size)

        print(f" -> Se ha recibido con éxito el mensaje: \n -> Mensaje: {msg}\n -> Desde {remitente}")
        server_socket.sendto(resolver(msg), remitente)

        if DEBUG: print("------------------------------------------------------------------------------------------")