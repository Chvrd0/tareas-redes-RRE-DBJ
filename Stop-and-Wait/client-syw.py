# cliente.py
import sys
from SocketTCP import SocketTCP

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python3 client-syw.py ip puerto < archivo")
        sys.exit(1)

    print(sys.argv)
    address = (sys.argv[1], int(sys.argv[2]))

    msg = sys.stdin.read()

    client = SocketTCP()
    client.connect(address)
    client.send(msg.encode())
    client.close()