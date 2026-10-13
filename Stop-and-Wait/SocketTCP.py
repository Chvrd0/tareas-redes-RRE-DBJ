import socket
DEBUG = True

class SocketTCP:
    # -------------------------------------------------------------------------------------------------
    # ------ Constantes -------------------------------------------------------------------------------
    # -------------------------------------------------------------------------------------------------
    ACK = 0b100
    SYN = 0b010
    FIN = 0b001

    SEQ_BITS = 29
    SEQ_MOD = 1 << SEQ_BITS
    SEQ_MASK = SEQ_MOD - 1

    HEADER_SIZE = 4
    
    # -------------------------------------------------------------------------------------------------
    # ----- Constructor -------------------------------------------------------------------------------
    # -------------------------------------------------------------------------------------------------
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.seq = None
        self.dest_addr = None
        self.remaining = 0
        self.buffer = b""

    # -------------------------------------------------------------------------------------------------
    # ----- 3-way handshake ---------------------------------------------------------------------------
    # -------------------------------------------------------------------------------------------------
    def bind(self, address):
        self.socket.bind(address)
        if DEBUG: print(f"BIND: Socket bound to {address}")

    # -------------------------------------------------------------------------------------------------
    def connect(self, address):
        """Handshake del lado cliente: SYN -> SYN+ACK -> ACK."""
        x = 0
        self.socket.settimeout(0.5)
        if DEBUG: print(f"CONNECT: Starting 3-way handshake with {address}")
        while True:
            self.socket.sendto(self.create_segment(self.SYN, x), address)
            if DEBUG: print(f"CONNECT: Sent SYN with seq={x} to {address}")
            try:
                data, new_addr = self.socket.recvfrom(20)
                
            except socket.timeout:
                if DEBUG: print("CONNECT: Timeout waiting for SYN+ACK, resending SYN")
                continue

            flags, seq, _ = self.parse_segment(data)
            if flags & self.SYN and flags & self.ACK and seq == self.add_seq(x, 1):
                if DEBUG: print(f"CONNECT: Received SYN+ACK with seq={seq} from {new_addr}")
                break

        self.dest_addr = new_addr
        self.socket.settimeout(1.5)
        while True:
            self.socket.sendto(self.create_segment(self.ACK, self.add_seq(x, 2)), self.dest_addr)
            if DEBUG: print(f"CONNECT: Sent ACK with seq={self.add_seq(x, 2)} to {self.dest_addr}")
            try:
                data, addr = self.socket.recvfrom(20)
            except socket.timeout:
                if DEBUG: print("CONNECT: Timeout waiting for ACK, breaking")
                break

        if DEBUG: print(f"CONNECT: Connection established with {self.dest_addr}")
        self.socket.settimeout(None)
        self.seq = self.add_seq(x, 3)

    # -------------------------------------------------------------------------------------------------
    def accept(self):
        """Espera un SYN en el socket de escucha y crea un nuevo SocketTCP
        para la comunicación real. Retorna (nuevo_socket, direccion_bindeada)."""
        if DEBUG: print("ACCEPT: Waiting for incoming connection...")
        while True:
            data, client_addr = self.socket.recvfrom(20)
            flags, x, _ = self.parse_segment(data)
            if flags & self.SYN and not flags & self.ACK:
                if DEBUG: print(f"ACCEPT: Received SYN with seq={x} from {client_addr}")
                break

        conn = SocketTCP()
        conn.bind((self.socket.getsockname()[0], 0))
        conn.dest_addr = client_addr
        conn_addr = conn.socket.getsockname()
        if DEBUG: print(f"ACCEPT: Created new socket with address {conn_addr}")

        while True:
            if DEBUG: print(f"ACCEPT: Sending SYN+ACK with seq={self.add_seq(x, 1)} to {client_addr}")
            conn.socket.sendto(
                self.create_segment(self.SYN | self.ACK, self.add_seq(x, 1)),
                client_addr
            )
            try:
                data, addr = conn.socket.recvfrom(20)
                flags, seq, _ = self.parse_segment(data)
                if addr == client_addr and flags & self.ACK and seq == self.add_seq(x, 2):
                    if DEBUG: print(f"ACCEPT: Received ACK with seq={seq} from {addr}, connection established")
                    break
            except socket.timeout:
                if DEBUG: print("ACCEPT: Timeout waiting for ACK, resending SYN+ACK")
                continue

        conn.seq = self.add_seq(x, 3)
        return conn, conn_addr

    # -------------------------------------------------------------------------------------------------
    # ----- Métodos de envío y recepción --------------------------------------------------------------
    # -------------------------------------------------------------------------------------------------
    def send_and_wait(self, data):
        """Envía un segmento y espera su ACK (x+1). Reenvía si vence el timeout."""
        segment = self.create_segment(0, self.seq, data)
        expected_ack = self.add_seq(self.seq, 1)

        self.socket.settimeout(0.5)
        while True:
            self.socket.sendto(segment, self.dest_addr)
            if DEBUG: print(f"SEND_AND_WAIT: Sent segment with seq={self.seq} to {self.dest_addr}")
            try:
                data, _ = self.socket.recvfrom(20)

            except socket.timeout:
                if DEBUG: print("SEND_AND_WAIT: Timeout waiting for ACK, resending segment")
                continue

            flags, ack, _ = self.parse_segment(data)
            
            if flags & self.ACK and ack == expected_ack:
                if DEBUG: print(f"SEND_AND_WAIT: Received ACK with seq={ack}, segment acknowledged")
                break

            if DEBUG: print(f"SEND_AND_WAIT: Received unexpected segment with seq={ack}, ignoring")

        self.socket.settimeout(None)
        self.seq = self.add_seq(self.seq, 2)

    # -------------------------------------------------------------------------------------------------
    def receive_and_confirm(self):
        """Recibe un segmento de datos nuevo, lo confirma y devuelve su payload."""
        self.socket.settimeout(None)
        if DEBUG: print("RECEIVE_AND_CONFIRM: Waiting for incoming segment...")

        while True:
            data, _ = self.socket.recvfrom(20)
            flags, seq, msg = self.parse_segment(data)
            if DEBUG: print(f"RECEIVE_AND_CONFIRM: Received segment with seq={seq}")

            if seq == self.seq:

                self.socket.sendto(
                    self.create_segment(self.ACK, self.add_seq(seq, 1)),
                    self.dest_addr
                )
                self.seq = self.add_seq(self.seq, 2)
                if DEBUG: print(f"RECEIVE_AND_CONFIRM: Sent ACK with seq={self.add_seq(seq, 1)}")
                return msg

            if seq == self.add_seq(self.seq, -2):

                self.socket.sendto(
                    self.create_segment(self.ACK, self.add_seq(seq, 1)),
                    self.dest_addr
                )
                if DEBUG: print(f"RECEIVE_AND_CONFIRM: Resent ACK with seq={self.add_seq(seq, 1)}")

    # -------------------------------------------------------------------------------------------------
    def send(self, msg):
        """Envía msg en trozos de 16 bytes, esperando ACK por cada uno."""

        if DEBUG: print(f"SEND: Sending message of length {len(msg)} bytes in chunks of 16 bytes")
        self.send_and_wait(len(msg).to_bytes(4, "big"))

        for i in range(0, len(msg), 16):
            if DEBUG: print(f"SEND: Sending chunk {i // 16 + 1} with length {min(16, len(msg) - i)} bytes")
            self.send_and_wait(msg[i:i + 16])

    # -------------------------------------------------------------------------------------------------
    def recv(self, size):
        """Retorna hasta `size` bytes del mensaje. Si faltan datos y el mensaje
        no ha terminado, se llama recursivamente para seguir recibiendo."""
        if DEBUG: print(f"RECV: Receiving up to {size} bytes")
        if self.remaining == 0 and not self.buffer:
            self.remaining = int.from_bytes(self.receive_and_confirm(), "big")
            if DEBUG: print(f"RECV: Starting new message reception with size {self.remaining} bytes")

        if not self.buffer and self.remaining > 0:
            if DEBUG: print(f"RECV: Buffer empty, receiving next chunk. Remaining bytes: {self.remaining}")
            chunk = self.receive_and_confirm()
            self.remaining -= len(chunk)
            self.buffer = chunk

        data, self.buffer = self.buffer[:size], self.buffer[size:]

        if len(data) < size and self.remaining > 0:
            data += self.recv(size - len(data))
        return data

    # -------------------------------------------------------------------------------------------------
    # ----- Métodos de cierre de la conexión ----------------------------------------------------------
    # -------------------------------------------------------------------------------------------------
    def clean(self):
        """Libera los recursos de la conexión."""
        if DEBUG: print("CLEAN: Closing socket and cleaning up resources")
        self.socket.close()
        self.seq = None
        self.dest_addr = None
        self.remaining = 0
        self.buffer = b""

    # -------------------------------------------------------------------------------------------------
    def close(self):
        """Inicia el cierre: FIN -> espera FIN+ACK -> envía ACK final."""
        x = self.seq
        if DEBUG: print(f"CLOSE: Initiating connection close with seq={x}")
        self.socket.settimeout(0.5)

        for i in range(3):
            if DEBUG: print(f"CLOSE: Sending FIN with seq={x} to {self.dest_addr}")
            self.socket.sendto(self.create_segment(self.FIN, x), self.dest_addr)
            try:
                data, addr = self.socket.recvfrom(20)
                flags, seq, _ = self.parse_segment(data)
                if (addr == self.dest_addr and flags & self.FIN and flags & self.ACK
                        and seq == self.add_seq(x, 1)):
                    if DEBUG: print(f"CLOSE: Received FIN+ACK with seq={seq} from {addr}")
                    break
            except socket.timeout:
                if DEBUG: print("CLOSE: Timeout waiting for FIN+ACK, resending FIN")
                continue

        for i in range(3):
            if DEBUG: print(f"CLOSE: Sending final ACK with seq={self.add_seq(x, 2)} to {self.dest_addr}")
            self.socket.sendto(self.create_segment(self.ACK, self.add_seq(x, 2)), self.dest_addr)
            try:
                data, addr = self.socket.recvfrom(20)
                flags, seq, _ = self.parse_segment(data)
                if (addr == self.dest_addr and flags & self.FIN and flags & self.ACK and seq == self.add_seq(x, 1)):
                    if DEBUG: print(f"CLOSE: Received FIN+ACK with seq={seq} from {addr}, responding with final ACK")
                    continue
            except socket.timeout:
                if DEBUG: print("CLOSE: Timeout waiting for final ACK, assuming connection closed")
                break

        if DEBUG: print("CLOSE: Connection closed, cleaning up resources")
        self.clean()

    # -------------------------------------------------------------------------------------------------
    def recv_close(self):
        """Lado que recibe el cierre: espera FIN -> envía FIN+ACK -> espera ACK."""
        while True:
            data, addr = self.socket.recvfrom(20)
            flags, x, _ = self.parse_segment(data)
            if addr == self.dest_addr and flags & self.FIN and x == self.seq:
                if DEBUG: print(f"RECV_CLOSE: Received FIN with seq={x} from {addr}")
                break

        self.socket.settimeout(0.5)
        for i in range(3):
            if DEBUG: print(f"RECV_CLOSE: Sending FIN+ACK with seq={self.add_seq(x, 1)} to {self.dest_addr}")
            self.socket.sendto(
                self.create_segment(self.FIN | self.ACK, self.add_seq(x, 1)),
                self.dest_addr
            )
            try:
                data, addr = self.socket.recvfrom(20)
                flags, seq, _ = self.parse_segment(data)
                if addr == self.dest_addr and flags & self.ACK and seq == self.add_seq(x, 2):
                    if DEBUG: print(f"RECV_CLOSE: Received ACK with seq={seq} from {addr}")
                    break
            except socket.timeout:
                if DEBUG: print("RECV_CLOSE: Timeout waiting for ACK, resending FIN+ACK")
                continue
        if DEBUG: print("RECV_CLOSE: Connection closed, cleaning up resources")
        self.clean()

    # -------------------------------------------------------------------------------------------------
    # ----- Métodos estáticos -------------------------------------------------------------------------
    # -------------------------------------------------------------------------------------------------
    @staticmethod
    def create_segment(flags, seq, data=b""):
        """Segmento = header de 4 bytes + data."""
        header = ((flags & 0b111) << SocketTCP.SEQ_BITS) | (seq & SocketTCP.SEQ_MASK)
        return header.to_bytes(SocketTCP.HEADER_SIZE, "big") + data

    # -------------------------------------------------------------------------------------------------
    @staticmethod
    def parse_segment(data):
        """Devuelve (flags, seq, payload) a partir de un datagrama recibido."""
        header = int.from_bytes(data[:SocketTCP.HEADER_SIZE], "big")
        flags = header >> SocketTCP.SEQ_BITS
        seq = header & SocketTCP.SEQ_MASK
        return flags, seq, data[SocketTCP.HEADER_SIZE:]

    # -------------------------------------------------------------------------------------------------
    @staticmethod
    def add_seq(seq, n=1):
        """Suma módulo 2^29 (por si el número da la vuelta)."""
        return (seq + n) % SocketTCP.SEQ_MOD
    # -------------------------------------------------------------------------------------------------