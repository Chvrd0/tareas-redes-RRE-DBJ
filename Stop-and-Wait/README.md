# Tarea 3: SocketTCP usando Stop & Wait

### Integrantes: David Ballester jorge y Ricardo Román Eriz

---

## Configuración del Servidor

1. **Configurar la IP del Proxy:**  
   Abra el archivo del servidor (`server-syw.py`) y defina en la variable `ip` la dirección IP correspondiente a la máquina donde se ejecutará el proxy:
   
   - Para pruebas locales en la misma máquina: `"localhost"` o `"127.0.0.1"`.
   - Para recibir peticiones desde otros dispositivos en la misma red: la dirección IP local de la máquina.

   ```python
   ip = "localhost"
   ```

---

## Ejecución del servidor

Abra una terminal, ubíquese en el directorio del proyecto y ejecute:

```bash
python3 server-syw.py
```

---

## Ejecución del cliente

Abra una terminal, ubíquese en el directorio del proyecto y ejecute:

```bash
python3 client-syw.py [IP-Destino] [Puerto-Destino] < [Ruta/A/Archivo]
```

---

## Modo DEBUG

Incialmente, los Sockets están configurados con el modo DEBUG activado. Para desactivarlo, entrar al archivo SocketTCP.py y cambiar:
```python
DEBUG = False
```

Con el modo DEBUG activado, se imprime en pantalla el flujo de trabajo de los Sockets.

---

## Simulación de pérdidas

Para simular pérdidas, use el siguiente comando:

```bash
 tc qdisc add dev lo root netem loss 20.0% delay 0.4s
```

Para detenerlas:

```bash
 sudo tc qdisc del dev lo root netem
```

---

## Flujo de Trabajo

### 3-Way Handshake

1. Servidor usa bind en la dirección definida para escuchar esa dirección esperando un cliente.

2. Cliente usa connect para establecer conexión con el servidor. Envía SYN para indicar la conexión y espera confirmación.

3. Servidor recibe SYN, crea un nuevo Socket para la comunicación y envía SYN + ACK desde este para confirmar conexión. Espera a la confirmación del cliente.

4. Cliente recibe SYN + ACK, establece la conexión y envía ACK para confirmar la misma.

Se usa settimeout de Sockets para esperar los mensajes. En caso de que se cumpla el tiempo, se reenvían los mensajes correspondientes. Para el último ACK del cliente, se espera: en caso de recibir nuevamente el SYN + ACK, se reenvía el ACK; si se termina el tiempo, se asume que el ACK llegó correctamente.


### Segmentos TCP y Headers

Para los headers, se usan 4 bytes extra de la siguiente forma

| 0 | 1 | 2 | 3 | 4 | 5 | 6 | ... | 31 | 
| --- | --- | --- | --- | --- | --- | --- | --- | --- | 
| SYN | ACK | FIN | N | U | M | E | R | O |

Para cada segmento enviado, se añade su sección de headers con su número de secuencia correspondiente. Se usan para verificar y confirmar los segmentos, y crear y cerrar conexiones.


### Envío y Recepción de mensajes.

1. El cliente envía un mensaje usando send. Primero, se envía el largo del mensaje y espera su confirmación.

2. El servidor recibe el largo y envía un ACK para confirmarlo.

3. El cliente recibe la confirmación. Divide el mensaje a enviar en fragmentos de 16 bytes. Envía cada fragmento y espera su respectiva confirmación para continuar. Una vez mandado todo el mensaje, retorna la función send.

4. El servidor recibe el primer fragmento, envía su ACK correspondiente y retorna. Para recibir completamente el mensaje, el servidor usa una función auxiliar que usa recv las veces necesarias hasta recibir completamente el mensaje.

5. El servidor escribe el mensaje completo en un archivo de destino.

En caso de que no se reciba la confirmación de un segmento (o se reciba un segmento errado), se reenvía el mismo. Lo mismo para las confirmaciones.


### Cierre de conexión

1. El cliente usa close para cerrar la conexión. Envía una señal FIN al servidor y espera su confirmación.

2. El servidor usa recv_close para esperar la señal del cliente. Recibe la señal FIN del cliente y envía FIN + ACK para confirmar. Espera la confirmación del cliente.

3. El cliente recibe FIN + ACK del servidor y envía su ACK para confirmar. Ambos Hosts limpian sus recursos.

En caso de pérdidas, se reenvían los mensajes correspondientes un máximo de 3 veces. Si se supera esta cantidad, se asume que la otra parte ya cerró la conexión.
