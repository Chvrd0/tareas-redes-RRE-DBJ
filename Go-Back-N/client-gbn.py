# cliente.py
import sys
from SocketTCP import SocketTCP

# ARQ a utilizar y si se usa control de congestion.
MODE = "go_back_n"
CONGESTION_CONTROL = True

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python3 client-gbn.py ip puerto < archivo")
        sys.exit(1)

    print(sys.argv)
    address = (sys.argv[1], int(sys.argv[2]))

    msg = sys.stdin.buffer.read()

    client = SocketTCP()
    client.connect(address)
    client.set_congestion_control(CONGESTION_CONTROL)
    client.send(msg, mode=MODE)
    client.close()

    print(f"Archivo enviado. Segmentos enviados (total): {client.number_of_sent_segments}")
