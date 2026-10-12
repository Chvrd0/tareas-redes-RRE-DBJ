import socket


class SocketTCP:
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
        self.remaining = 0
        self.buffer = b""


    def bind(self, address):
        self.socket.bind(address)

    def connect(self, address):
        """Handshake del lado cliente: SYN -> SYN+ACK -> ACK."""
        x = 0
        self.socket.sendto(self.create_segment(self.SYN, x), address)

        data, new_addr = self.socket.recvfrom(1024)
        flags, seq, _ = self.parse_segment(data)
        if not (flags & self.SYN and flags & self.ACK) or seq != self.add_seq(x, 1):
            raise ConnectionError("Handshake fallido: se esperaba SYN+ACK")

        self.dest_addr = new_addr
        self.socket.sendto(self.create_segment(self.ACK, self.add_seq(x, 2)), new_addr)
        self.seq = self.add_seq(x, 3)

    def accept(self):
        """Espera un SYN en el socket de escucha y crea un nuevo SocketTCP
        para la comunicación real. Retorna (nuevo_socket, direccion_bindeada)."""
        while True:
            data, client_addr = self.socket.recvfrom(1024)
            flags, x, _ = self.parse_segment(data)
            if flags & self.SYN and not flags & self.ACK:
                break

        conn = SocketTCP()
        conn.bind((self.socket.getsockname()[0], 0))
        conn.dest_addr = client_addr
        conn_addr = conn.socket.getsockname()

        conn.socket.sendto(
            self.create_segment(self.SYN | self.ACK, self.add_seq(x, 1)),
            client_addr
        )

        while True:
            data, addr = conn.socket.recvfrom(1024)
            flags, seq, _ = self.parse_segment(data)
            if addr == client_addr and flags & self.ACK and seq == self.add_seq(x, 2):
                break

        conn.seq = self.add_seq(x, 3)
        return conn, conn_addr

    def send_and_wait(self, data):
        """Envía un segmento y espera su ACK (x+1). Reenvía si vence el timeout."""
        segment = self.create_segment(0, self.seq, data)
        expected_ack = self.add_seq(self.seq, 1)

        self.socket.settimeout(0.5)
        while True:
            self.socket.sendto(segment, self.dest_addr)

            try:
                data, _ = self.socket.recvfrom(1024)

            except socket.timeout:
                continue

            flags, ack, _ = self.parse_segment(data)
            
            if flags & self.ACK and ack == expected_ack:
                break

        self.socket.settimeout(None)

        self.seq = self.add_seq(self.seq, 2)

    def receive_and_confirm(self):
        """Recibe un segmento de datos nuevo, lo confirma y devuelve su payload."""
        self.socket.settimeout(None)

        while True:
            data, _ = self.socket.recvfrom(1024)
            flags, seq, msg = self.parse_segment(data)

            if seq == self.seq:

                self.socket.sendto(
                    self.create_segment(self.ACK, self.add_seq(seq, 1)),
                    self.dest_addr
                )
                self.seq = self.add_seq(self.seq, 2)
                return msg

            if seq == self.add_seq(self.seq, -2):

                self.socket.sendto(
                    self.create_segment(self.ACK, self.add_seq(seq, 1)),
                    self.dest_addr
                )

    def send(self, msg):
        """Envía msg en trozos de 16 bytes, esperando ACK por cada uno."""

        self.send_and_wait(len(msg).to_bytes(4, "big"))

        for i in range(0, len(msg), 16):
            self.send_and_wait(msg[i:i + 16])


    def recv(self, size):
        """Retorna hasta `size` bytes del mensaje. Si faltan datos y el mensaje
        no ha terminado, se llama recursivamente para seguir recibiendo."""
        if self.remaining == 0 and not self.buffer:
            self.remaining = int.from_bytes(self.receive_and_confirm(), "big")

        if not self.buffer and self.remaining > 0:
            chunk = self.receive_and_confirm()
            self.remaining -= len(chunk)
            self.buffer = chunk

        data, self.buffer = self.buffer[:size], self.buffer[size:]

        if len(data) < size and self.remaining > 0:
            data += self.recv(size - len(data))
        return data


    @staticmethod
    def create_segment(flags, seq, data=b""):
        """Segmento = header de 4 bytes + data."""
        header = ((flags & 0b111) << SocketTCP.SEQ_BITS) | (seq & SocketTCP.SEQ_MASK)
        return header.to_bytes(SocketTCP.HEADER_SIZE, "big") + data

    @staticmethod
    def parse_segment(data):
        """Devuelve (flags, seq, payload) a partir de un datagrama recibido."""
        header = int.from_bytes(data[:SocketTCP.HEADER_SIZE], "big")
        flags = header >> SocketTCP.SEQ_BITS
        seq = header & SocketTCP.SEQ_MASK
        return flags, seq, data[SocketTCP.HEADER_SIZE:]

    @staticmethod
    def add_seq(seq, n=1):
        """Suma módulo 2^29 (por si el número da la vuelta)."""
        return (seq + n) % SocketTCP.SEQ_MOD