# Tarea 1: Servidor Proxy HTTP en Python

Este proyecto implementa un servidor Proxy HTTP básico utilizando sockets orientados a conexión en Python. Permite interceptar el tráfico HTTP, bloquear dominios no deseados, inyectar cabeceras personalizadas y filtrar o reemplazar palabras prohibidas en el cuerpo de las respuestas HTML antes de reenviarlas al cliente.


---

## Configuración del Servidor

1. **Configurar la IP del Proxy:**  
   Abra el archivo del servidor (`proxyHTTP.py`) y defina en la variable `ip` la dirección IP correspondiente a la máquina donde se ejecutará el proxy:
   
   - Para pruebas locales en la misma máquina: `"localhost"` o `"127.0.0.1"`.
   - Para recibir peticiones desde otros dispositivos en la misma red: la dirección IP local de la máquina.

   ```python
   ip = "localhost"
   ```

2. **Archivo de configuración (`config.json`):**  
   El archivo `config.json` ya se encuentra en el repositorio y permite gestionar las listas de filtrado y modificación:
   - `blocked`: Lista de dominios cuyo acceso será denegado.
   - `forbidden_words`: Lista de objetos con pares clave-valor que indican la palabra a buscar y su reemplazo.
   - `heads`: Cabeceras HTTP personalizadas a inyectar en las peticiones y respuestas.

---

## Configuración del Navegador Web

Para que el tráfico HTTP del navegador pase a través del servidor proxy:

1. Configure el proxy en su navegador web siguiendo la guía disponible en:  
   https://es.ccm.net/ordenadores/redes/3750-como-configurar-un-proxy-en-tu-navegador-web/

2. Parámetros de conexión a ingresar:
   - **Servidor / Host / Dirección:** La dirección IP configurada en el servidor.
   - **Puerto:** `8000`.
   - **Protocolo:** HTTP.

---

## Ejecución del Servidor

Abra una terminal, ubíquese en el directorio del proyecto y ejecute:

```bash
python3 proxyHTTP.py
```

---

## Registros en Consola (Logs)

Durante la ejecución, el servidor mostrará en tiempo real los mensajes recibidos, las interceptaciones de dominios y las modificaciones del contenido.

### 1. Inicialización y espera de clientes
```text
Creando socket - Servidor
... Esperando clientes
```

### 2. Mensaje recibido del cliente
Muestra la estructura del mensaje HTTP enviado por el cliente tras ser parseado:
```text
MENSAJE RECIBIDO DEL CLIENTE:
 {'header': {'start-line': 'GET http://ejemplo.com/ HTTP/1.1', 'Host': 'ejemplo.com', 'User-Agent': 'Mozilla/5.0 ...'}, 'body': None}
```

### 3. Dominio bloqueado
Si el dominio solicitado coincide con alguno de los especificados en la lista `blocked` de `config.json`, el servidor responde un código 403 Forbidden junto con la página de bloqueo:
```text
DOMINIO BLOQUEADO:
 HTTP/1.1 403 Forbidden
Content-Type: text/html
Content-Length: 172

<!DOCTYPE html>
<html lang="es">
<head>
     <meta charset="UTF-8">
     <title>LOL</title>
</head>
<body>
     <h1>Lo siento, página prohibida</h1>
     <img src="403.jpg" > 
</body>
```

### 4. Petición permitida y filtrado de contenido
Cuando la petición es válida, el proxy la reenvía al servidor web de destino, recibe la respuesta, aplica los reemplazos configurados y envía el resultado modificado al cliente:
```text
MENSAJE RECIBIDO DEL SERVIDOR:
 {'header': {'start-line': 'HTTP/1.1 200 OK', 'Content-Type': 'text/html', 'Content-Length': '245'}, 'body': '<html>... texto original con palabra_prohibida ...</html>'}

MENSAJE DEL SERVIDOR FILTRADO:
 {'header': {'start-line': 'HTTP/1.1 200 OK', 'Content-Type': 'text/html', 'Content-Length': '238'}, 'body': '<html>... texto con el reemplazo aplicado ...</html>'}

conexión con ('127.0.0.1', 54321) ha sido cerrada
```