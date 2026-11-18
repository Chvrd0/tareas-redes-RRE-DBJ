# Fragmentación y re-ensamblado de datagramas IP sobre UDP

Extiende el mini-Internet de la actividad de *forwarding* para que los enlaces
tengan un **MTU** (Maximum Transmission Unit). Antes de hacer *forward*, cada
router fragmenta el paquete según el MTU del enlace de salida, y el router de
destino re-ensambla los fragmentos (indexados por `ID`) antes de imprimir el
mensaje. Se mantiene el control de **TTL** y el balanceo **Round-Robin** de la
actividad anterior.

---

## 1. Estructura del header IP (16 bytes fijos)

| Campo    | Bytes   | Descripción |
|----------|---------|-------------|
| IP       | `[0:4]` | Dirección IPv4 de destino final (4 octetos `a.b.c.d`). |
| Puerto   | `[4:6]` | Puerto de destino final (big-endian). |
| TTL      | `[6]`   | Time To Live (1 byte sin signo). |
| ID       | `[7:9]` | Identificador del datagrama, común a todos sus fragmentos. |
| Offset   | `[9:11]`| Offset **en bytes** del fragmento dentro del mensaje original. |
| Tamaño   | `[11:15]`| Tamaño del mensaje de este fragmento, sin header (4 bytes). |
| FLAG     | `[15]`  | More-Fragment: `1` si quedan más fragmentos, `0` si es el último. |
| Mensaje  | `[16:]` | Payload en bytes. |

Decisiones de diseño:

* **Offset en bytes** (no en octetos de a 8), tal como permite el enunciado.
* **ID** en 2 bytes (0–65535), **Offset** en 2 bytes, **Tamaño** en 4 bytes y
  **FLAG** en 1 byte (entero `0`/`1`).
* El payload se maneja como **bytes** en todo el camino y solo se decodifica al
  imprimirlo en destino, para poder fragmentar sin romper caracteres multibyte.
* Con el MTU más chico de la topología (`50`), cada fragmento lleva
  `50 - 16 = 34` bytes de datos.

---

## 2. Tabla de rutas con MTU

Cada línea agrega el MTU del enlace de salida:

```text
<Red_CIDR> <Puerto_Inicio> <Puerto_Fin> <IP_Next_Hop> <Puerto_Next_Hop> <MTU>
```

`check_routes` retorna `((ip, puerto), MTU)` del siguiente salto, o `None`. Si
hay varias rutas para el mismo destino, alterna con Round-Robin. Soporta líneas
sin MTU (asume un MTU grande que no fragmenta).

Topología de 5 routers (`rutas/v3/`):

```
MTU=100        MTU=50
R1 <------> R2 <------> R3
             ^           ^
   MTU=80 |            | MTU=55
             v           v
            R4 <------> R5
                MTU=140
```

---

## 3. Funciones principales (`router.py`)

* `parse_packet(IP_packet)` / `create_packet(parsed)`: (de)serializan el header
  de 16 bytes.
* `fragment_IP_packet(IP_packet, MTU)`: retorna una lista de fragmentos (largo
  ≥ 1). Si el paquete cabe en el MTU retorna `[IP_packet]`; si no, parte el
  mensaje en trozos de `MTU - 16` bytes y re-configura Offset, Tamaño y FLAG.
  Si recibe un fragmento, lo **re-fragmenta** respetando su offset y flag base.
* `reassemble_IP_packet(fragment_list)`: ordena por offset (tolera desorden y
  duplicados) y retorna el paquete IP completo, o `None` si faltan fragmentos.

---

## 4. Uso

### Levantar los routers (una terminal por router)

```bash
python3 router.py 127.0.0.1 8881 rutas/v3/rutas_R1_v3_mtu.txt
python3 router.py 127.0.0.1 8882 rutas/v3/rutas_R2_v3_mtu.txt
python3 router.py 127.0.0.1 8883 rutas/v3/rutas_R3_v3_mtu.txt
python3 router.py 127.0.0.1 8884 rutas/v3/rutas_R4_v3_mtu.txt
python3 router.py 127.0.0.1 8885 rutas/v3/rutas_R5_v3_mtu.txt
```

### Enviar un datagrama

El emisor arma **un** paquete (offset 0, flag 0) con el contenido de `msg.txt` y
lo inyecta en el router de entrada, que lo fragmenta según corresponda:

```bash
python3 msg_sender.py <IP_dest>:<Puerto_dest>:<TTL>:<ID> <IP_router> <Puerto_router>
# Ejemplo: enviar desde R1 hacia R5 con TTL=10 e ID=347
python3 msg_sender.py 127.0.0.1:8885:10:347 127.0.0.1 8881
```

---

## 5. Pruebas

### Pruebas de red

* **Fragmentación directa:** enviar a `R2` (`8882`) un mensaje > 84 bytes entrando
  por `R1`; `R1` lo fragmenta (MTU 100) y `R2` re-ensambla e imprime el mensaje.
* **Extremo a extremo:** enviar a `R5` (`8885`) entrando por `R1`; los fragmentos
  cruzan varios enlaces (re-fragmentándose en los MTU más chicos y llegando
  desordenados por Round-Robin) y `R5` los re-ensambla.
* **TTL:** con `TTL` bajo el paquete se descarta en el camino
  (`Se recibió paquete ... con TTL 0.`), igual que en la actividad anterior.

---

## 6. Declaración de uso de Inteligencia Artificial

Se utilizó apoyo de IA para la documentación (docstrings, comentarios y este
README) y para la implementación de la fragmentación/re-ensamblado y su
integración con el *forwarding* y el control de TTL/Round-Robin.
