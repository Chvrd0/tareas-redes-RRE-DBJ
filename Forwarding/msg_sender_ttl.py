import socket
import sys

address = ("localhost", 5000)

socket_sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
socket_sender.bind(address)


headers = sys.argv[1].split(":")

ip_envio = sys.argv[2]
puerto_envio = int(sys.argv[3])

archivo = "msg.txt"

with open(archivo, "r") as f:
    for line in f:
        packet = bytes([int(octeto) for octeto in headers[0].split(".")]) + int(headers[1]).to_bytes(2, "big") + int(headers[2]).to_bytes(1, "big") + line.encode()
        socket_sender.sendto(packet, (ip_envio, puerto_envio))


