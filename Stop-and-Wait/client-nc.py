import socket

print('Creando socket - Cliente')

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

address = ('localhost', 5000)

path = input("Archivo a ingresar: ") 
end_msg = '\r\n\r\n'

with open(path, "r") as file:
    msg = file.read()

encoded_msg = (msg + end_msg).encode()

print(f" -> Enviando su mensaje...\n {msg}\n")

for i in range(0, len(msg), 16):
    client_socket.sendto(encoded_msg[i:i+16], address)

print(" -> Mensaje Enviado.")

buff_size = 1024
rsp, address = client_socket.recvfrom(buff_size)

decoded_msg = rsp.decode()
print(f" -> Respuesta del servidor: \n{decoded_msg}\n -> Desde: {address}")

