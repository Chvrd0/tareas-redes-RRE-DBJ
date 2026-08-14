import socket
import json
# esta función se encarga de recibir el mensaje completo desde el cliente
# en caso de que el mensaje sea más grande que el tamaño del buffer 'buff_size', esta función va esperar a que
# llegue el resto. Para saber si el mensaje ya llegó por completo, se busca el caracter de fin de mensaje (parte de nuestro protocolo inventado)


# Recibe un mensaje HTTP y lo convierte en un diccionario tipo:
# { header: Diccionario con los head,   body: Body del mensaje}
def parse_HTTP_message(http_message: bytes, json = None):
    http = http_message.decode()
    head_body = http.split("\r\n\r\n")
    header = head_body[0]
    if len(head_body) == 2:
        body = head_body[1]
    else:
        body = None

    h_dt = {
        "start line": header.split("\r\n")[0]
    }

    for h in header.split("\r\n")[1:]:
        h_dt[h.split(": ")[0]] = h.split(": ")[1]

    if json:
        for i in json:
            h_dt[i] = json[i]


    ds = {
        "header": h_dt,
        "body": body
    }

    return ds

# a = 'HTTP/1.1 201 Created\r\nContent-Type: application/json\r\nLocation: http://example.com/users/123\r\n\r\n{"message": "New user created", "user": {"id": 123, "firstName": "Example", "lastName": "Person", "email": "bsmth@example.com"}}'
# print(parse_HTTP_message(a.encode()))



def create_HTTP_message(parseHTTP: dict):
    header = parseHTTP["header"]
    body = parseHTTP["body"]

    msgHTTP = header["start line"] + "\r\n"

    for k in header:
        if k == "start line": continue
        msgHTTP += f"{k}: {header[k]}\r\n"

    msgHTTP += f"\r\n\r\n{body}"
    return msgHTTP.encode()

# b = parse_HTTP_message(a.encode())
# print(create_HTTP_message(b).decode())


def respuesta_HTTP(json = None):
    ans = {
        "header":{
            "start line": "HTTP/1.1 200 OK",
            "Content-Type": "text/html",
            "Content-Length": "201"
        },
        "body": '<!DOCTYPE html>\n<html lang="es">\n<head>\n     <meta charset="UTF-8">\n     <title>CC4303</title>\n</head>\n<body>\n     <h1>Prueba de Respuesta</h1>\n     <h2>David Ballester y Ricardo Román</h2>\n</body>\n'
    }
    if json:
        for i in json:
            ans["header"][i] = json[i]
    
    return create_HTTP_message(ans)
    



def receive_full_message(connection_socket, buff_size, end_sequence):
 
    # recibimos la primera parte del mensaje
    recv_message = connection_socket.recv(buff_size)
    full_message = recv_message
 
    # verificamos si llegó el mensaje completo o si aún faltan partes del mensaje
    is_end_of_message = contains_end_of_message(full_message.decode(), end_sequence)
 
    # entramos a un while para recibir el resto y seguimos esperando información
    # mientras el buffer no contenga secuencia de fin de mensaje
    while not is_end_of_message:
        # recibimos un nuevo trozo del mensaje
        recv_message = connection_socket.recv(buff_size)
 
        # lo añadimos al mensaje "completo"
        full_message += recv_message
 
        # verificamos si es la última parte del mensaje
        is_end_of_message = contains_end_of_message(full_message.decode(), end_sequence)
 
    # removemos la secuencia de fin de mensaje, esto entrega un mensaje en string
    full_message = remove_end_of_message(full_message.decode(), end_sequence)
 
    # finalmente retornamos el mensaje
    return full_message
 
 
def contains_end_of_message(message, end_sequence):
    return message.endswith(end_sequence)

 
def remove_end_of_message(full_message, end_sequence):
    index = full_message.rfind(end_sequence)
    return full_message[:index]
 
if __name__ == "__main__":
    # definimos el tamaño del buffer de recepción y la secuencia de fin de mensaje
    buff_size = 4

    # una peticion no tiene body, solo se recibe hasta que exista un doble salto de linea.
    end_of_message = "\r\n\r\n"

    new_socket_address = ('localhost', 8000)
     
    print('Creando socket - Servidor')
    # armamos el socket
    # los parámetros que recibe el socket indican el tipo de conexión
    # socket.SOCK_STREAM = socket orientado a conexión
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
     
    # le indicamos al server socket que debe atender peticiones en la dirección address
    # para ello usamos bind
    server_socket.bind(new_socket_address)
     
    # luego con listen (función de sockets de python) le decimos que puede
    # tener hasta 3 peticiones de conexión encoladas
    # si recibiera una 4ta petición de conexión la va a rechazar
    server_socket.listen(3)
    with open("config.json") as f:
        server_info = json.load(f)
     
    # nos quedamos esperando a que llegue una petición de conexión
    print('... Esperando clientes')
    while True:
        # cuando llega una petición de conexión la aceptamos
        # y se crea un nuevo socket que se comunicará con el cliente
        new_socket, new_socket_address = server_socket.accept()
     
        # luego recibimos el mensaje usando la función que programamos
        # esta función entrega el mensaje en string (no en bytes) y sin el end_of_message
        recv_message = receive_full_message(new_socket, buff_size, end_of_message)
        parsed_msg = parse_HTTP_message(recv_message.encode(), server_info)
        print(parsed_msg)
     
        # respondemos indicando que recibimos el mensaje
        response_message = respuesta_HTTP(server_info)
        new_socket.send(response_message)
     
        # el mensaje debe pasarse a bytes antes de ser enviado, para ello usamos encode
     
        # cerramos la conexión
        # notar que la dirección que se imprime indica un número de puerto distinto al 5000
        new_socket.close()
        print(f"conexión con {new_socket_address} ha sido cerrada")
     
        # seguimos esperando por si llegan otras conexiones