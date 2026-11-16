import socket

address = ("localhost", 5000)

socket_sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
socket_sender.bind(address)

while True:
    ip_destino = input("Ingrese la IP de destino: ")
    puerto_destino = int(input("Ingrese el puerto de destino: "))

    ip_envio = input("Ingrese la IP de envío: ")
    puerto_envio = int(input("Ingrese el puerto de envío: "))

    msg = input("Ingrese el mensaje a enviar: ")

    packet = bytes([int(octeto) for octeto in ip_destino.split(".")]) + puerto_destino.to_bytes(2, "big") + msg.encode()

    socket_sender.sendto(packet, (ip_envio, puerto_envio))
