# Tarea 2 Resolver DNS

Este proyecto implementa un servidor DNS Resolver básico utilizando sockets UDP en Python. Su función principal es resolver nombres de dominio mediante una búsqueda recursiva, comenzando directamente desde el servidor raíz (`198.41.0.4`) y descendiendo por la jerarquía DNS hasta encontrar la dirección IP solicitada (respuestas tipo A). Además, el servidor optimiza su funcionamiento manteniendo un historial de las últimas 20 consultas para implementar un sistema de caché dinámico, el cual almacena y responde de manera instantánea a las peticiones de los 3 dominios más consultados.

---

## Configuración del Servidor

1. **Configurar la IP del Servidor:**  
   Abra el archivo del servidor (`resolver.py`) y defina en la variable `IP_VM` la dirección IP correspondiente a la máquina donde se ejecutará el resolver. Por defecto está configurado para pruebas locales:
   
   ```python
   IP_VM = "localhost"
   ```

2. **Instalación de dependencias:**  
   El proyecto requiere la librería externa `dnslib` para desempaquetar, parsear y crear los paquetes con el formato del protocolo DNS. Instálela ejecutando el siguiente comando:
   
   ```bash
   pip install dnslib
   ```

---

## Ejecución del Servidor

Abra una terminal, ubíquese en el directorio donde se encuentra el archivo `resolver.py` y ejecute:

```bash
python3 resolver.py
```

---

## Registros en Consola (Logs)

Gracias a la variable `DEBUG = True`, durante la ejecución el servidor mostrará en tiempo real el paso a paso de las resoluciones DNS y las interacciones con el caché.

### 1. Inicialización
Al iniciar, el script levanta el socket UDP y se pone a la escucha de clientes en el puerto 8000:
```text
Creando socket - Servidor DNS en localhost:8000
```

### 2. Consulta recursiva
Cuando llega una consulta que debe ser resuelta (porque no está en el top 3 del caché), el servidor muestra el rastro de la búsqueda recursiva a través de los distintos Name Servers:
```text
(debug) Consultando 'example.com.' a '.' con dirección IP '198.41.0.4'
(debug) Consultando 'example.com.' a 'a.gtld-servers.net.' con dirección IP '192.5.6.30'
(debug) Consultando 'example.com.' a 'ns1.example.com.' con dirección IP '93.184.216.34'
```

### 3. Respuesta desde caché
Si el dominio solicitado se encuentra actualmente entre los 3 más frecuentes del historial, el servidor evita el proceso recursivo y responde inmediatamente con la IP guardada en memoria:
```text
(debug) RESPONDIENDO DESDE CACHE: example.com. -> 93.184.216.34
```