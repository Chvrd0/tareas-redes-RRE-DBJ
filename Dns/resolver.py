import socket
IP_VM = "localhost"

if __name__ == "__main__":
    buff_size = 10000
    address = ('localhost', 8000)

    print('Creando socket - Servidor')

    server_socket =  socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(address)

    while True:
        msg, remitente = server_socket.recvfrom(buff_size)

        print(f" -> Se ha recibido con éxito el mensaje: \n -> Mensaje: {msg}\n -> Desde {remitente}")