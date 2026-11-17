# Simulador de Enrutamiento de Paquetes sobre UDP

Este proyecto implementa una simulación de red de capa de transporte/red utilizando sockets UDP (`SOCK_DGRAM`) en Python. Permite levantar múltiples instancias de routers en distintos puertos locales, configurar topologías mediante tablas de enrutamiento en texto plano, balancear tráfico mediante *Round-Robin* y prevenir bucles de red mediante un campo **TTL** (*Time To Live*).

---

## 1. Flujo de Trabajo de los Routers

Existen dos implementaciones de router: `router.py` (sin control de saltos) y `routerTTL.py` (con control de saltos máximos). Ambos siguen un ciclo de vida basado en eventos sobre datagramas UDP:

1. **Inicialización:** El proceso recibe `<IP>`, `<Puerto>` y `<Archivo_Rutas>` por línea de comandos, crea un socket UDP IPv4 (`AF_INET`, `SOCK_DGRAM`) y lo enlaza (`bind`) a la dirección local especificada.
2. **Recepción y Deserialización (`parse_packet`):** En un bucle infinito (`recvfrom(1024)`), el router extrae la cabecera personalizada de los primeros bytes del datagrama:
   * **Versión base (`router.py` — 6 bytes de cabecera):**
     * `Bytes [0:4]`: Dirección IPv4 de destino final (4 octetos).
     * `Bytes [4:6]`: Puerto de destino final en formato *Big-Endian* (2 bytes).
     * `Bytes [6:]`: Carga útil (*payload*) del mensaje en UTF-8.
   * **Versión con TTL (`routerTTL.py` — 7 bytes de cabecera):**
     * `Bytes [0:4]`: Dirección IPv4 de destino final.
     * `Bytes [4:6]`: Puerto de destino final en formato *Big-Endian*.
     * `Byte  [6]`: Valor actual del **TTL** (1 byte sin signo).
     * `Bytes [7:]`: Carga útil (*payload*) del mensaje en UTF-8.
3. **Verificación de TTL (solo `routerTTL.py`):** Antes de procesar el destino, si `ttl == 0`, el router descarta el paquete inmediatamente e informa la expiración en consola.
4. **Entrega Local vs. Reenvío:**
   * **Entrega local:** Si el puerto de destino en la cabecera coincide con el puerto en el que escucha el router actual, se considera que el paquete llegó a su destino y se imprime el cuerpo del mensaje en salida estándar.
   * **Reenvío (*Forwarding*):** Si el puerto destino es distinto, el router consulta su tabla de rutas mediante `check_routes()`.
     * Si no existe ruta válida (`None`), el paquete se descarta y se registra el error.
     * Si existe un siguiente salto (*next hop*), `routerTTL.py` decrementa el campo `ttl` en `1`, vuelve a serializar el paquete (`create_packet`) y lo envía al salto seleccionado con `sendto()`.

---

## 2. Uso de los Clientes Emisores (*Senders*)

Los emisores permiten inyectar paquetes en un **router de entrada** (primer salto) indicando dentro de la cabecera cuál es el **destino final** que debe resolver la red.

### `msg_sender.py` (Interactivo, sin TTL)
Compatible con `router.py`. Abre un socket UDP en `localhost:5000` y solicita los datos de forma interactiva por consola en cada envío:
1. **Puerto de destino:** Puerto del router final al que va dirigido el mensaje (se codifica en la cabecera).
2. **Puerto de envío:** Puerto del router inicial que recibirá el datagrama directamente.
3. **Mensaje:** Texto a transmitir.

```bash
python3 msg_sender.py
```

### `msg_sender_ttl.py` (Por lotes desde archivo, con TTL)
Compatible con `routerTTL.py`. Lee el archivo `msg.txt` línea por línea y envía cada línea como un paquete independiente hacia el router de inicio:

```bash
python3 msg_sender_ttl.py <IP_Destino>:<Puerto_Destino>:<TTL> <IP_Router_Inicio> <Puerto_Router_Inicio>
```

* `<IP_Destino>:<Puerto_Destino>:<TTL>`: Define la cabecera lógica del paquete (destino final y saltos máximos permitidos).
* `<IP_Router_Inicio> <Puerto_Router_Inicio>`: Dirección física del socket del primer router al que se inyecta el tráfico.

---

## 3. Funcionamiento de *Round-Robin* para Elegir Rutas

La función `check_routes(routes_file_name, destination_address)` implementa un balanceo de carga cíclico (*Round-Robin*) cuando existen múltiples caminos hacia un mismo destino:

1. **Formato de tabla de rutas:** Cada línea válida del archivo de rutas sigue la estructura:
   ```text
   <Red_CIDR> <Puerto_Inicio> <Puerto_Fin> <IP_Next_Hop> <Puerto_Next_Hop>
   ```
2. **Filtrado de candidatas:** El router lee el archivo completo y recopila en una lista `candidatas` **todas** las tuplas `(IP_Next_Hop, Puerto_Next_Hop)` cuyo rango `[Puerto_Inicio, Puerto_Fin]` contenga al puerto de destino del paquete.
3. **Rotación por área:** Se utiliza un diccionario global en memoria:
   ```python
   ultimo_indice_por_area: dict[tuple[str, tuple[tuple[str, int], ...]], int]
   ```
   La clave combina el nombre del archivo de rutas y la tupla inmutable de rutas candidatas encontradas para ese destino. En cada consulta:
   * Se obtiene el índice actual `indice` (por defecto `0`).
   * Se actualiza el estado para la próxima consulta mediante `(indice + 1) % len(candidatas)`.
   * Se retorna `candidatas[indice]`, distribuyendo equitativamente los paquetes consecutivos entre todos los enlaces disponibles.

---

## 4. Ejemplos de Uso y Pruebas

> **Convenciones generales para las pruebas:**
> * Todos los archivos de rutas siguen la estructura `rutas/vX/rutas_RN_vX.txt`.
> * Cada router debe ejecutarse en una **terminal independiente**.
> * La asignación estándar de puertos es `R0: 8880`, `R1: 8881`, `R2: 8882`, `R3: 8883`, `R4: 8884`, `R5: 8885`, `R6: 8886` y `Router Default: 7000`.

---

### 4.1. Pruebas sin TTL (`router.py` + `msg_sender.py`)

#### Versión `v1`: 2 Routers conectados entre sí (`R1 <-> R2`)
Topología directa entre `R1` (`8881`) y `R2` (`8882`).

* **Terminal 1 (R1):**
  ```bash
  python3 router.py 127.0.0.1 8881 rutas/v1/rutas_R1_v1.txt
  ```
* **Terminal 2 (R2):**
  ```bash
  python3 router.py 127.0.0.1 8882 rutas/v1/rutas_R2_v1.txt
  ```
* **Terminal 3 (Emisor — enviar desde R1 hacia R2):**
  ```bash
  python3 msg_sender.py
  # Ingrese el puerto de destino: 8882
  # Ingrese el puerto de envío: 8881
  # Ingrese el mensaje a enviar: Hola R2 desde R1
  ```

---

#### Versión `v2`: 3 Routers con bucle de enrutamiento (`A <-> B <-> C`)
Topología de tres nodos (`R1` = A en `8881`, `R2` = B en `8882`, `R3` = C en `8883`), donde `R2` tiene configurada su ruta hacia `8883` apuntando de regreso a `8881`, provocando un bucle infinito entre `R1` y `R2`.

* **Terminal 1 (R1 / Nodo A):**
  ```bash
  python3 router.py 127.0.0.1 8881 rutas/v2/rutas_R1_v2.txt
  ```
* **Terminal 2 (R2 / Nodo B):**
  ```bash
  python3 router.py 127.0.0.1 8882 rutas/v2/rutas_R2_v2.txt
  ```
* **Terminal 3 (R3 / Nodo C):**
  ```bash
  python3 router.py 127.0.0.1 8883 rutas/v2/rutas_R3_v2.txt
  ```
* **Terminal 4 (Emisor — intentar llegar a C/`8883` entrando por A/`8881`):**
  ```bash
  python3 msg_sender.py
  # Ingrese el puerto de destino: 8883
  # Ingrese el puerto de envío: 8881
  # Ingrese el mensaje a enviar: Mensaje atrapado en bucle
  ```
  *Resultado esperado:* Los terminales de `R1` y `R2` mostrarán redirecciones infinitas entre `8881` y `8882` sin que el paquete llegue jamás a `R3` (`8883`).

---

#### Versión `v3`: 5 Routers conectados en malla parcial (`R1` a `R5`)
Red de 5 nodos (`8881` a `8885`) con múltiples rutas alternativas y balanceo *Round-Robin*.

* **Terminal 1 (R1):**
  ```bash
  python3 router.py 127.0.0.1 8881 rutas/v3/rutas_R1_v3.txt
  ```
* **Terminal 2 (R2):**
  ```bash
  python3 router.py 127.0.0.1 8882 rutas/v3/rutas_R2_v3.txt
  ```
* **Terminal 3 (R3):**
  ```bash
  python3 router.py 127.0.0.1 8883 rutas/v3/rutas_R3_v3.txt
  ```
* **Terminal 4 (R4):**
  ```bash
  python3 router.py 127.0.0.1 8884 rutas/v3/rutas_R4_v3.txt
  ```
* **Terminal 5 (R5):**
  ```bash
  python3 router.py 127.0.0.1 8885 rutas/v3/rutas_R5_v3.txt
  ```
* **Terminal 6 (Emisor — enviar desde R1/`8881` hasta R5/`8885`):**
  ```bash
  python3 msg_sender.py
  # Ingrese el puerto de destino: 8885
  # Ingrese el puerto de envío: 8881
  # Ingrese el mensaje a enviar: Mensaje de R1 a R5 en v3
  ```

---

#### Versión `v4`: 7 Routers con nodos extremos `R0` y `R6` (`R0` a `R6`)
Amplía la topología `v3` agregando `R0` (`8880`, conectado a `R1` y `R2`) y `R6` (`8886`, conectado a `R2` y `R3`).

* **Terminal 1 (R0):**
  ```bash
  python3 router.py 127.0.0.1 8880 rutas/v4/rutas_R0_v4.txt
  ```
* **Terminal 2 (R1):**
  ```bash
  python3 router.py 127.0.0.1 8881 rutas/v4/rutas_R1_v4.txt
  ```
* **Terminal 3 (R2):**
  ```bash
  python3 router.py 127.0.0.1 8882 rutas/v4/rutas_R2_v4.txt
  ```
* **Terminal 4 (R3):**
  ```bash
  python3 router.py 127.0.0.1 8883 rutas/v4/rutas_R3_v4.txt
  ```
* **Terminal 5 (R4):**
  ```bash
  python3 router.py 127.0.0.1 8884 rutas/v4/rutas_R4_v4.txt
  ```
* **Terminal 6 (R5):**
  ```bash
  python3 router.py 127.0.0.1 8885 rutas/v4/rutas_R5_v4.txt
  ```
* **Terminal 7 (R6):**
  ```bash
  python3 router.py 127.0.0.1 8886 rutas/v4/rutas_R6_v4.txt
  ```
* **Terminal 8 (Emisor — enviar desde R1/`8881` hasta R5/`8885`):**
  ```bash
  python3 msg_sender.py
  # Ingrese el puerto de destino: 8885
  # Ingrese el puerto de envío: 8881
  # Ingrese el mensaje a enviar: Mensaje de R1 a R5 en topologia de 7 routers
  ```

---

#### Versión `v5`: 6 Routers (5 internos + 1 Router por Defecto en puerto `7000`)
Los 5 routers originales (`8881` a `8885`) redirigen todo tráfico cuyo destino esté fuera de `8881..8885` hacia el router por defecto ubicado en `127.0.0.1:7000`.

* **Terminal 1 (R1):**
  ```bash
  python3 router.py 127.0.0.1 8881 rutas/v5/rutas_R1_v5.txt
  ```
* **Terminal 2 (R2):**
  ```bash
  python3 router.py 127.0.0.1 8882 rutas/v5/rutas_R2_v5.txt
  ```
* **Terminal 3 (R3):**
  ```bash
  python3 router.py 127.0.0.1 8883 rutas/v5/rutas_R3_v5.txt
  ```
* **Terminal 4 (R4):**
  ```bash
  python3 router.py 127.0.0.1 8884 rutas/v5/rutas_R4_v5.txt
  ```
* **Terminal 5 (R5):**
  ```bash
  python3 router.py 127.0.0.1 8885 rutas/v5/rutas_R5_v5.txt
  ```
* **Terminal 6 (Router por Defecto en `localhost:7000`):**
  ```bash
  python3 router.py localhost 7000 rutas/v5/rutas_Rdefault_v5.txt
  ```
* **Terminal 7 (Emisor — enviar a un puerto externo como `7000` o `9999` desde R1/`8881`):**
  ```bash
  python3 msg_sender.py
  # Ingrese el puerto de destino: 7000
  # Ingrese el puerto de envío: 8881
  # Ingrese el mensaje a enviar: Paquete capturado por ruta por defecto
  ```

---

### 4.2. Pruebas con Control de Saltos (`routerTTL.py` + `msg_sender_ttl.py`)

Para todas las pruebas siguientes, asegúrate de tener un archivo `msg.txt` en el directorio de ejecución.

#### Caso A: `v3` con `TTL = 1` desde un extremo a otro (`R1` $\rightarrow$ `R5`)
Comprueba que un paquete con `TTL = 1` no alcanza un destino que requiere múltiples saltos (`R1 -> R2 -> R3/R4 -> R5`).

1. **Levantar los 5 routers de `v3` con `routerTTL.py` (Terminales 1 a 5):**
   ```bash
   python3 routerTTL.py 127.0.0.1 8881 rutas/v3/rutas_R1_v3.txt
   python3 routerTTL.py 127.0.0.1 8882 rutas/v3/rutas_R2_v3.txt
   python3 routerTTL.py 127.0.0.1 8883 rutas/v3/rutas_R3_v3.txt
   python3 routerTTL.py 127.0.0.1 8884 rutas/v3/rutas_R4_v3.txt
   python3 routerTTL.py 127.0.0.1 8885 rutas/v3/rutas_R5_v3.txt
   ```
2. **Enviar desde `R1` (`8881`) hacia `R5` (`8885`) con `TTL = 1` (Terminal 6):**
   ```bash
   python3 msg_sender_ttl.py 127.0.0.1:8885:1 127.0.0.1 8881
   ```
   *Resultado esperado:* `R1` recibe el paquete con `TTL = 1`, lo decrementa a `0` y lo reenvía a `R2`. Al recibirlo, `R2` imprime `Se recibió paquete 127.0.0.1 con TTL 0.` y lo descarta. El mensaje nunca llega a `R5`.

---

#### Caso B: `v2` con `TTL = 10` (extinción de paquetes en bucles)
Comprueba que el mecanismo de `TTL` evita que los datagramas circulen indefinidamente en la topología con bucle `v2`.

1. **Levantar los 3 routers de `v2` con `routerTTL.py` (Terminales 1 a 3):**
   ```bash
   python3 routerTTL.py 127.0.0.1 8881 rutas/v2/rutas_R1_v2.txt
   python3 routerTTL.py 127.0.0.1 8882 rutas/v2/rutas_R2_v2.txt
   python3 routerTTL.py 127.0.0.1 8883 rutas/v2/rutas_R3_v2.txt
   ```
2. **Enviar desde `R1` (`8881`) hacia `R3` (`8883`) con `TTL = 10` (Terminal 4):**
   ```bash
   python3 msg_sender_ttl.py 127.0.0.1:8883:10 127.0.0.1 8881
   ```
   *Resultado esperado:* El paquete rebota 10 veces entre `R1` (`8881`) y `R2` (`8882`) decrementando su `TTL` en cada salto hasta llegar a `0`, momento en que es descartado automáticamente.

---

#### Caso C: `v3` con `TTL = 10` y archivo grande (orden de llegada por *Round-Robin*)
Comprueba el comportamiento del enrutamiento multicamino y el orden de recepción en el destino cuando se transmiten cientos de líneas consecutivas.

1. **Generar un archivo `msg.txt` grande (por ejemplo, 500 mensajes numerados):**
   ```bash
   seq -f "Mensaje numero %03g" 1 500 > msg.txt
   ```
2. **Con los 5 routers de `v3` ejecutándose con `routerTTL.py`, enviar el lote desde `R1` (`8881`) hasta `R5` (`8885`) con `TTL = 10`:**
   ```bash
   python3 msg_sender_ttl.py 127.0.0.1:8885:10 127.0.0.1 8881
   ```
   *Resultado esperado:* Todos los paquetes cuentan con saltos suficientes (`TTL = 10`) para alcanzar `R5` (`8885`). Debido a que `R2`, `R3` y `R4` alternan rutas mediante *Round-Robin* sobre sockets UDP no orientados a conexión, los caminos tienen distinta cantidad de saltos (por ejemplo, `R1 -> R2 -> R3 -> R5` frente a `R1 -> R2 -> R4 -> R2 -> ...`), provocando que los mensajes lleguen desordenados a la consola de `R5`.

## 5. Declaración de Uso de Inteligencia Artificial

En el desarrollo de este proyecto se utilizó apoyo de herramientas de Inteligencia Artificial (Gemini) para las siguientes tareas específicas:

* **Documentación:** Redacción de *docstrings*, comentarios explicativos en los scripts de Python (`router.py`, `routerTTL.py`, `msg_sender.py`, `msg_sender_ttl.py`) y estructuración de este archivo `README.md`.
* **Asistencia en lógica de enrutamiento:** Apoyo en el diseño e implementación del mecanismo de selección cíclica de rutas (*Round-Robin*) por área de destino en la función `check_routes`.