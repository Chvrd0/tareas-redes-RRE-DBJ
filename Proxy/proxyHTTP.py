import socket
import json

# Constantes de configuración global
FOTO = '"403.jpg"'
ip = "localhost"

# Lectura de las reglas y configuraciones (dominios bloqueados, palabras prohibidas y cabeceras)
with open("config.json") as f:
    JSON_INFO = f
    SERVER_INFO = json.load(f)


def parse_HTTP_message(http_message: bytes, json=None):
    """
    Decodifica y descompone un mensaje HTTP en bytes en una estructura de diccionario.

    Separa los encabezados del cuerpo utilizando el delimitador estándar (\r\n\r\n).
    Extrae la línea de inicio (start-line) y procesa cada par clave-valor de las cabeceras.
    Si se proporciona una configuración JSON con cabeceras adicionales, las incorpora
    o sobrescribe en el diccionario resultante.

    Args:
        http_message (bytes): Flujo de bytes correspondiente al mensaje HTTP.
        json (dict, opcional): Configuración con cabeceras personalizadas a inyectar.

    Returns:
        dict: Diccionario estructurado con claves 'header' y 'body'.
    """
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


def create_HTTP_message(parseHTTP: dict):
    """
    Reconstruye un mensaje HTTP en formato de bytes a partir de un diccionario estructurado.

    Concatena la línea de inicio, todas las cabeceras formateadas y el cuerpo del mensaje,
    retornando la cadena resultante codificada en bytes.

    Args:
        parseHTTP (dict): Estructura del mensaje que contiene 'header' y 'body'.

    Returns:
        bytes: Mensaje HTTP listo para su transmisión por la red.
    """
    header = parseHTTP["header"]
    body = parseHTTP["body"]

    msgHTTP = header["start-line"] + "\r\n"

    for k in header:
        if k == "start-line": continue
        msgHTTP += f"{k}: {header[k]}\r\n"

    msgHTTP += f"\r\n\r\n{body}"
    return msgHTTP.encode()


def respuesta_HTTP():
    """
    Construye la respuesta HTTP 403 Forbidden para dominios restringidos.

    Genera una página HTML básica que informa sobre el bloqueo e incluye
    la referencia a la imagen configurada, empaquetándola en una respuesta HTTP válida.

    Returns:
        bytes: Mensaje de error 403 serializado en bytes.
    """
    ans = {
        "header": {
            "start-line": "HTTP/1.1 403 Forbidden",
            "Content-Type": "text/html",
            "Content-Length": "172"
        },
        "body": f'<!DOCTYPE html>\n<html lang="es">\n<head>\n     <meta charset="UTF-8">\n     <title>LOL</title>\n</head>\n<body>\n     <h1>Lo siento, página prohibida</h1>\n     <img src={FOTO} > \n</body>\n'
    }
    return create_HTTP_message(ans)


def headerEnded(message):
    """
    Comprueba si se ha recibido la totalidad de los encabezados HTTP verificando
    la presencia de la secuencia delimitadora \r\n\r\n.

    Args:
        message (bytes): Fragmento o acumulado de bytes leídos del socket.

    Returns:
        bool: True si las cabeceras han terminado, False en caso contrario.
    """
    return b"\r\n\r\n" in message


def cutHeader(full_message):
    """
    Recorta un mensaje HTTP conservando únicamente la sección de cabeceras.

    Busca el delimitador final de las cabeceras y corta el flujo de bytes en esa posición.

    Args:
        full_message (bytes): Mensaje HTTP acumulado en bytes.

    Returns:
        bytes: Porción del mensaje correspondiente a los encabezados.
    """
    index = full_message.rfind(b"\r\n\r\n")
    return full_message[:index+5]


def receive_HTTP_message(socket, buff_size):
    """
    Lee un mensaje HTTP completo desde un socket TCP de forma progresiva.

    Realiza lecturas parciales hasta identificar el fin de las cabeceras. Si se detecta
    el encabezado 'Content-Length', calcula la longitud del cuerpo y ejecuta una lectura
    adicional para asegurar que el contenido completo sea recibido.

    Args:
        socket (socket.socket): Socket TCP activo.
        buff_size (int): Tamaño del buffer para cada lectura parcial.

    Returns:
        bytes: Mensaje HTTP recibido en su totalidad.
    """
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


def forbiddenReplace(parseHTTP: dict, json=None):
    """
    Aplica el filtro de palabras prohibidas sobre el cuerpo del mensaje y actualiza su tamaño.

    Busca y reemplaza las palabras especificadas en la configuración dentro del contenido
    del cuerpo, recalculando la cabecera 'Content-Length' para evitar inconsistencias
    en el tamaño del mensaje transmitido.

    Args:
        parseHTTP (dict): Mensaje HTTP descompuesto en cabeceras y cuerpo.
        json (dict, opcional): Configuración con las reglas de reemplazo.

    Returns:
        dict: Mensaje estructurado con el contenido filtrado y el Content-Length actualizado.
    """
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
    """
    Extrae y limpia el nombre de dominio a partir de la línea de petición HTTP.

    Solo procesa solicitudes GET, eliminando prefijos de protocolo (http:// o https://)
    y diagonales finales para estandarizar el dominio.

    Args:
        st_ln (str): Línea inicial de la solicitud HTTP (ej. 'GET http://ejemplo.com/ HTTP/1.1').

    Returns:
        str: Nombre de dominio limpio, o cadena vacía si no es una solicitud GET válida.
    """
    if st_ln.split(" ")[0] != "GET":
        return ""
    domain = st_ln.split(" ")[1]
    domain = domain.replace("http://", "")
    domain = domain.replace("https://", "")
    if domain.endswith("/"):
        domain = domain[:-1]
    return domain


def blockedDomain(parseHTTP: dict, json=None):
    """
    Determina si el dominio solicitado se encuentra dentro de la lista de sitios bloqueados.

    Args:
        parseHTTP (dict): Mensaje HTTP estructurado.
        json (dict, opcional): Configuración con el listado de dominios restringidos.

    Returns:
        bool: True si el dominio está bloqueado, False en caso contrario.
    """
    to = getDomain(parseHTTP["header"]['start-line'])
    if json:
        domains = []
        if "blocked" in json:
            domains = json["blocked"]
        return to in domains
    return False


if __name__ == "__main__":
    # Configuración inicial del socket servidor del proxy
    buff_size = 4
    proxy_socket_address = (f'{ip}', 8000)
     
    print('Creando socket - Servidor')
    proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_socket.bind(proxy_socket_address)
    proxy_socket.listen(3)
     
    # Bucle principal para escuchar y atender conexiones entrantes
    print('... Esperando clientes')
    while True:
        # Se acepta la conexión del cliente y se recibe su solicitud HTTP
        client_socket, client_socket_address = proxy_socket.accept()
     
        recv_message = receive_HTTP_message(client_socket, buff_size)
        parsed_msg = parse_HTTP_message(recv_message, SERVER_INFO)

        print(f"\nMENSAJE RECIBIDO DEL CLIENTE:\n {parsed_msg}")

        # Si el sitio solicitado está bloqueado, se responde un error 403 y se corta la comunicación
        if blockedDomain(parsed_msg, SERVER_INFO):
            res = respuesta_HTTP()
            print(f"\nDOMINIO BLOQUEADO:\n {res.decode()}")

            client_socket.send(res)
            client_socket.close()
            continue
        
        # Validamos que sea una petición GET soportada y extraemos el dominio de destino
        website = getDomain(parsed_msg["header"]['start-line'])

        if website == "":
            client_socket.close()
            continue
        
        # Conexión hacia el servidor web de destino mediante el host indicado en las cabeceras
        server_address = (parsed_msg["header"]["Host"], 80)
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect(server_address)

        # Se reenvía la petición del cliente hacia el servidor remoto
        server_socket.send(create_HTTP_message(parsed_msg))

        # Recepción de la respuesta original del servidor remoto
        res = parse_HTTP_message(receive_HTTP_message(server_socket, buff_size), SERVER_INFO)
        print(f"\nMENSAJE RECIBIDO DEL SERVIDOR:\n {res}")

        # Aplicación del filtro de contenido antes de entregar la respuesta al cliente
        filtered_msg = forbiddenReplace(res, SERVER_INFO)
        print(f"\nMENSAJE DEL SERVIDOR FILTRADO:\n {filtered_msg}")

        # Se envía la respuesta modificada de vuelta al cliente
        client_socket.send(create_HTTP_message(filtered_msg))
    
        # Cierre de sockets para finalizar la sesión actual
        server_socket.close()
        client_socket.close()
        print(f"conexión con {client_socket_address} ha sido cerrada")
     
        # Continúa a la siguiente iteración a la espera de nuevas solicitudes