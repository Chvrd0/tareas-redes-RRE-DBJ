import socket
from dnslib import DNSRecord
from dnslib.dns import CLASS, QTYPE
import dnslib 
IP_VM = "localhost"



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




if __name__ == "__main__":
    buff_size = 10000
    address = ('localhost', 8000)

    print('Creando socket - Servidor')

    server_socket =  socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(address)

    while True:
        msg, remitente = server_socket.recvfrom(buff_size)

        print(f" -> Se ha recibido con éxito el mensaje: \n -> Mensaje: {msg}\n -> Desde {remitente}")

        print(f"-> Mensaje parseado: {parseDNS(msg)}")