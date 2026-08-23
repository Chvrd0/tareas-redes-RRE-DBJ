import socket
import json

FOTO = '"403.jpg"'
ip = "localhost"

with open("config.json") as f:
        JSON_INFO = f
        SERVER_INFO = json.load(f)

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
        "start-line": header.split("\r\n")[0]
    }

    for h in header.split("\r\n")[1:]:
        h_dt[h.split(": ")[0]] = h.split(": ")[1]

    if json:
        for i in json["heads"]:
            h_dt[i] = json["heads"][i]


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

    msgHTTP = header["start-line"] + "\r\n"

    for k in header:
        if k == "start-line": continue
        msgHTTP += f"{k}: {header[k]}\r\n"

    msgHTTP += f"\r\n\r\n{body}"
    return msgHTTP.encode()

# b = parse_HTTP_message(a.encode())
# print(create_HTTP_message(b).decode())


def respuesta_HTTP():
    ans = {
        "header":{
            "start-line": "HTTP/1.1 403 Forbidden",
            "Content-Type": "text/html",
            "Content-Length": "172"
        },
        "body": f'<!DOCTYPE html>\n<html lang="es">\n<head>\n     <meta charset="UTF-8">\n     <title>LOL</title>\n</head>\n<body>\n     <h1>Lo siento, página prohibida</h1>\n     <img src={FOTO} > \n</body>\n'
    }
    return create_HTTP_message(ans)
    


def receive_HTTP_message(socket, buff_size):
    msg = socket.recv(buff_size)
    full_msg = msg

    header = False

    while not header:
        msg = socket.recv(buff_size)
        full_msg += msg
        header = headerEnded(full_msg)

    if "Content-Length" in parse_HTTP_message(full_msg)["header"]:
        contenido = parse_HTTP_message(full_msg)["header"]["Content-Length"]
        full_msg = cutHeader(full_msg) + socket.recv(int(contenido))
    return full_msg
 


def headerEnded(message):
    return b"\r\n\r\n" in message

 
def cutHeader(full_message):
    index = full_message.rfind(b"\r\n\r\n")
    return full_message[:index+5]



def forbiddenReplace(parseHTTP: dict, json = None):
    body = parseHTTP["body"]
    head = parseHTTP["header"]
    cl = int(head["Content-Length"])

    if json:
        if "forbidden_words" in json:
            words = json["forbidden_words"]
        
        for b in words:
            word, replacement = list(b.keys())[0], list(b.values())[0]
            cl += ((len(replacement) * body.count(word)) - (len(word) * body.count(word)))
            body = body.replace(word, replacement)

    head["Content-Length"] = str(cl)
    filtered_body = {
            "header": head,
            "body": body
        }
    print(filtered_body)
    return filtered_body

def getDomain(st_ln):
    if st_ln.split(" ")[0] != "GET":
        return ""
    domain = st_ln.split(" ")[1]
    domain = domain.replace("http://", "")
    domain = domain.replace("https://", "")
    if domain.endswith("/"):
        domain = domain[:-1]
    return domain


def blockedDomain(parseHTTP: dict, json = None):
    to = getDomain(parseHTTP["header"]['start-line'])
    if json:
        domains = []
        if "blocked" in json:
            domains = json["blocked"]
        return to in domains
    return False


if __name__ == "__main__":
    # definimos el tamaño del buffer de recepción y la secuencia de fin de mensaje
    buff_size = 4


    proxy_socket_address = (f'{ip}', 8000)
     
    print('Creando socket - Servidor')
    # armamos el socket
    proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
     
    # hacemos bind
    proxy_socket.bind(proxy_socket_address)
     
    # limitamos las peticiones
    proxy_socket.listen(3)
     
    # nos quedamos esperando a que llegue una petición de conexión
    print('... Esperando clientes')
    while True:
        # cuando llega una petición de conexión la aceptamos
        # y se crea un nuevo socket que se comunicará con el cliente
        client_socket, client_socket_address = proxy_socket.accept()
     
        # luego recibimos el mensaje usando la nueva funcion
        recv_message = receive_HTTP_message(client_socket, buff_size)
        parsed_msg = parse_HTTP_message(recv_message, SERVER_INFO)

        print(f"\nMENSAJE RECIBIDO DEL CLIENTE:\n {parsed_msg}")

        # si el dominio está bloqueado mandamos respuesta al cliente y cerramos conexión
        if blockedDomain(parsed_msg, SERVER_INFO):
            res = respuesta_HTTP()
            print(f"\nDOMINIO BLOQUEADO:\n {res.decode()}")

            client_socket.send(res)
            client_socket.close()
            continue
        
        # Nuevo socket apuntando a la direccion solicitada por el mensaje recibido
        website = getDomain(parsed_msg["header"]['start-line'])

        if website == "":
            client_socket.close()
            continue
        
        server_address = (parsed_msg["header"]["Host"], 80)
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect(server_address)

        # Manda a la dirección solicitada el mensaje tal cual se recibe
        server_socket.send(create_HTTP_message(parsed_msg))

        # Se recibe la respuesta del socket a la direccion solicitada y se cierra la conexión
        res = parse_HTTP_message(receive_HTTP_message(server_socket, buff_size), SERVER_INFO)
        print(f"\nMENSAJE RECIBIDO DEL SERVIDOR:\n {res}")

        filtered_msg = forbiddenReplace(res, SERVER_INFO)
        print(f"\nMENSAJE DEL SERVIDOR FILTRADO:\n {filtered_msg}")

        # Se responde sin cambiar lo que respondió la dirección solicitada
        client_socket.send(create_HTTP_message(filtered_msg))
    
     
        # cerramos las conexiones
        server_socket.close()
        client_socket.close()
        print(f"conexión con {client_socket_address} ha sido cerrada")
     
        # seguimos esperando por si llegan otras conexiones