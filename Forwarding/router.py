import sys
import socket


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python3 router.py <IP> <Puerto> <Rutas>")
        sys.exit(1)

    ip = sys.argv[1]
    puerto = int(sys.argv[2])
    address = (ip, puerto)

    router = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    router.bind(address)

    rutas = sys.argv[3]
    print(f"Router iniciado en {ip}:{puerto} con rutas: {rutas}")

    

    while True:
        data, addr = router.recvfrom(1024)
        print(f"Mensaje recibido de {addr}: {data.decode()}")
