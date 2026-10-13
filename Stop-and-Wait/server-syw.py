import SocketTCP

IP = "localhost"

def receive_full_message(connection_socket, buff_size):
 
    recv_message = connection_socket.recv(buff_size)
    full_message = recv_message
 
    # verificamos si llegó el mensaje completo o si aún faltan partes del mensaje
    is_end_of_message = connection_socket.remaining == -1
 
    # entramos a un while para recibir el resto y seguimos esperando información
    # mientras el buffer no contenga secuencia de fin de mensaje
    while not is_end_of_message:
        # recibimos un nuevo trozo del mensaje
        recv_message = connection_socket.recv(buff_size)
 
        # lo añadimos al mensaje "completo"
        full_message += recv_message
 
        # verificamos si es la última parte del mensaje
        is_end_of_message = connection_socket.remaining == -1
 
 
    # finalmente retornamos el mensaje
    return full_message.decode()

if __name__ == "__main__":
    buff_size = 16
    address = (IP, 5000)

    print('Creando socket - Servidor')

    server_socket =  SocketTCP.SocketTCP()
    server_socket.bind(address)

    print("Esperando cliente...")
    new_connection, new_address = server_socket.accept()

    print(f"Cliente conectado: {new_address}")

    msg = receive_full_message(new_connection, buff_size)

    with open("utils/received_message.txt", "w") as file:
        file.write(msg)

    print("Mensaje completo! Guardado en utils/received_message.txt")

    new_connection.recv_close()


    