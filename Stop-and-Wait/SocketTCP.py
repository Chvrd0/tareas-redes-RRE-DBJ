import socket


class SocketUDP:
    # Flags (3 bits más significativos del header)
    ACK = 0b100
    SYN = 0b010
    FIN = 0b001

    # Número de secuencia (29 bits restantes)
    SEQ_BITS = 29
    SEQ_MOD = 1 << SEQ_BITS
    SEQ_MASK = SEQ_MOD - 1

    HEADER_SIZE = 4

    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.seq = None
        self.dest_addr = None


    def bind(self, address):
        self.socket.bind(address)

    def connect(self, address):
        """Handshake del lado cliente: SYN -> SYN+ACK -> ACK."""
        x = 0
        self.dest_addr = address

        self.socket.sendto(self.create_segment(self.SYN, x), address)

        data, _ = self.socket.recvfrom(1024)
        flags, seq, _ = self.parse_segment(data)
        if not (flags & self.SYN and flags & self.ACK) or seq != self.add_seq(x, 1):
            raise ConnectionError("Handshake fallido: se esperaba SYN+ACK")

        self.socket.sendto(self.create_segment(self.ACK, self.add_seq(x, 2)), address)

        self.seq = self.add_seq(x, 3)

    def accept(self):
        """Handshake del lado servidor: espera SYN -> SYN+ACK -> espera ACK.
        Devuelve la dirección del cliente."""
        while True:
            data, client_addr = self.socket.recvfrom(1024)
            flags, x, _ = self.parse_segment(data)
            if flags & self.SYN and not flags & self.ACK:
                break

        self.dest_addr = client_addr

        self.socket.sendto(
            self.create_segment(self.SYN | self.ACK, self.add_seq(x, 1)),
            client_addr
        )

        data, _ = self.socket.recvfrom(1024)
        flags, seq, _ = self.parse_segment(data)
        if not (flags & self.ACK) or seq != self.add_seq(x, 2):
            raise ConnectionError("Handshake fallido: se esperaba ACK final")

        self.seq = self.add_seq(x, 3)
        return client_addr

    @staticmethod
    def create_segment(flags, seq, data=b""):
        """Segmento = header de 4 bytes + data."""
        header = ((flags & 0b111) << SocketUDP.SEQ_BITS) | (seq & SocketUDP.SEQ_MASK)
        return header.to_bytes(SocketUDP.HEADER_SIZE, "big") + data

    @staticmethod
    def parse_segment(data):
        """Devuelve (flags, seq, payload) a partir de un datagrama recibido."""
        header = int.from_bytes(data[:SocketUDP.HEADER_SIZE], "big")
        flags = header >> SocketUDP.SEQ_BITS
        seq = header & SocketUDP.SEQ_MASK
        return flags, seq, data[SocketUDP.HEADER_SIZE:]

    @staticmethod
    def add_seq(seq, n=1):
        """Suma módulo 2^29 (por si el número da la vuelta)."""
        return (seq + n) % SocketUDP.SEQ_MOD