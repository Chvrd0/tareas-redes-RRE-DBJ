import socket

IP = "localhost"

def receive_full_message(connection_socket, buff_size, end_sequence):
 
    # recibimos la primera parte del mensaje
    recv_message, fromm = connection_socket.recvfrom(buff_size)
    full_message = recv_message
 
    # verificamos si llegó el mensaje completo o si aún faltan partes del mensaje
    is_end_of_message = contains_end_of_message(full_message.decode(), end_sequence)
 
    # entramos a un while para recibir el resto y seguimos esperando información
    # mientras el buffer no contenga secuencia de fin de mensaje
    while not is_end_of_message:
        # recibimos un nuevo trozo del mensaje
        recv_message, a = connection_socket.recvfrom(buff_size)
        print(recv_message.decode())
 
        # lo añadimos al mensaje "completo"
        full_message += recv_message
 
        # verificamos si es la última parte del mensaje
        is_end_of_message = contains_end_of_message(full_message.decode(), end_sequence)
 
    # removemos la secuencia de fin de mensaje, esto entrega un mensaje en string
    full_message = remove_end_of_message(full_message.decode(), end_sequence)
 
    # finalmente retornamos el mensaje
    return full_message, fromm

def contains_end_of_message(message, end_sequence):
    return message.endswith(end_sequence)
 
 
def remove_end_of_message(full_message, end_sequence):
    index = full_message.rfind(end_sequence)
    return full_message[:index]


if __name__ == "__main__":
    buff_size = 16
    end_character = '\r\n\r\n'
    address = (IP, 5000)

    print('Creando socket - Servidor')

    server_socket =  socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(address)

    while True:
        msg, remitente = receive_full_message(server_socket, buff_size, end_character)

        print("\nMensaje completo!")

        rsp = f"Se recibio correctamente el mensaje. "

        server_socket.sendto(rsp.encode(), remitente)

    