import socket
import bisect
from socketUDP import SocketUDP
from slidingWindowCC import SlidingWindowCC
from CongestionControl import CongestionControl

DEBUG = True
# Modo debug especifico para la ventana de congestion (Parte 3).
DEBUG_CC = True

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

    # Parametros de Go-Back-N / control de congestion.
    MSS = 8                 # tamaño maximo del area de datos de un segmento (bytes)
    GBN_WINDOW = 8          # tamaño de ventana fijo (en segmentos) cuando NO hay control de congestion
    GBN_TIMEOUT = 0.5       # timeout fijo para Go-Back-N (segundos)

    # -------------------------------------------------------------------------------------------------
    # ----- Constructor -------------------------------------------------------------------------------
    # -------------------------------------------------------------------------------------------------
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.seq = None
        self.dest_addr = None
        # Bytes del mensaje en curso que todavia no se reciben desde la red.
        # 0 (y buffer vacio) significa que no hay un mensaje en curso.
        self.remaining = 0
        # Bytes ya recibidos desde la red pero aun no entregados al llamador
        # (sobrantes cuando un trozo excede el buff_size pedido en recv).
        self.buffer = b""
        # ----- Control de congestion (Parte 3) -----
        # Indica si send_using_go_back_n debe usar control de congestion.
        self.congestion_control_on = False
        # Objeto CongestionControl, se crea al iniciar un envio con control on.
        self.congestion_controler = None
        # Contador de segmentos enviados (incluye retransmisiones), util para
        # comparar Go-Back-N con y sin control de congestion.
        self.number_of_sent_segments = 0
        # Ultimo segmento ACK enviado por el receptor. Permite reconfirmar datos
        # retransmitidos durante recv_close() sin depender del ARQ usado.
        self.last_ack_segment = None

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
                
            except (socket.timeout, ConnectionResetError):
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
            except (socket.timeout, ConnectionResetError):
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

        conn.socket.settimeout(0.5)
        tries = 0
        while True:
            if DEBUG: print(f"ACCEPT: Sending SYN+ACK with seq={self.add_seq(x, 1)} to {client_addr}")
            conn.socket.sendto(
                self.create_segment(self.SYN | self.ACK, self.add_seq(x, 1)),
                client_addr
            )
            try:
                data, addr = conn.socket.recvfrom(20)
            except (socket.timeout, ConnectionResetError):
                tries += 1
                if tries >= 3:
                    # Tercer timeout: asumimos que el ACK final se perdio y que
                    # el cliente ya dio por establecida la conexion.
                    if DEBUG: print("ACCEPT: Timeout limit reached, assuming final ACK lost, connection established")
                    break
                if DEBUG: print("ACCEPT: Timeout waiting for ACK, resending SYN+ACK")
                continue

            flags, seq, _ = self.parse_segment(data)
            if addr == client_addr and flags & self.ACK and seq == self.add_seq(x, 2):
                if DEBUG: print(f"ACCEPT: Received ACK with seq={seq} from {addr}, connection established")
                break
            # Caso borde: se perdio el ACK final del handshake y el cliente ya
            # empezo a enviar datos. El primer segmento de datos usa seq=x+3.
            # Lo tomamos como confirmacion implicita; ese segmento se
            # retransmitira (Stop & Wait) y lo recibira recv().
            if addr == client_addr and seq == self.add_seq(x, 3):
                if DEBUG: print("ACCEPT: Received first data segment, handshake assumed complete")
                break

        conn.socket.settimeout(None)
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

            except (socket.timeout, ConnectionResetError):
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
            try:
                data, _ = self.socket.recvfrom(20)
            except ConnectionResetError:
                # Windows puede lanzar esto por un ICMP de un envio previo;
                # lo ignoramos y seguimos esperando el segmento.
                continue
            flags, seq, msg = self.parse_segment(data)
            if DEBUG: print(f"RECEIVE_AND_CONFIRM: Received segment with seq={seq}")

            if seq == self.seq:

                self.last_ack_segment = self.create_segment(self.ACK, self.add_seq(seq, 1))
                self.socket.sendto(self.last_ack_segment, self.dest_addr)
                self.seq = self.add_seq(self.seq, 2)
                if DEBUG: print(f"RECEIVE_AND_CONFIRM: Sent ACK with seq={self.add_seq(seq, 1)}")
                return msg

            if seq == self.add_seq(self.seq, -2):

                self.last_ack_segment = self.create_segment(self.ACK, self.add_seq(seq, 1))
                self.socket.sendto(self.last_ack_segment, self.dest_addr)
                if DEBUG: print(f"RECEIVE_AND_CONFIRM: Resent ACK with seq={self.add_seq(seq, 1)}")

    # -------------------------------------------------------------------------------------------------
    # ----- Despachadores por modo (ARQ) --------------------------------------------------------------
    # -------------------------------------------------------------------------------------------------
    def send(self, message, mode="stop_and_wait"):
        """Envía message usando el ARQ indicado por mode."""
        if mode == "stop_and_wait":
            self.send_using_stop_and_wait(message)
        elif mode == "go_back_n":
            self.send_using_go_back_n(message)

    # -------------------------------------------------------------------------------------------------
    def recv(self, buff_size, mode="stop_and_wait"):
        """Recibe hasta buff_size bytes usando el ARQ indicado por mode."""
        if mode == "stop_and_wait":
            return self.recv_using_stop_and_wait(buff_size)
        elif mode == "go_back_n":
            return self.recv_using_go_back_n(buff_size)

    # -------------------------------------------------------------------------------------------------
    def set_congestion_control(self, value):
        """Setter para activar/desactivar el control de congestion en Go-Back-N."""
        self.congestion_control_on = value
        if DEBUG: print(f"SET_CONGESTION_CONTROL: congestion_control_on = {value}")

    # -------------------------------------------------------------------------------------------------
    # ----- Stop & Wait -------------------------------------------------------------------------------
    # -------------------------------------------------------------------------------------------------
    def send_using_stop_and_wait(self, msg):
        """Envía msg en trozos de 16 bytes, esperando ACK por cada uno."""

        if DEBUG: print(f"SEND: Sending message of length {len(msg)} bytes in chunks of 16 bytes")
        self.send_and_wait(len(msg).to_bytes(4, "big"))

        for i in range(0, len(msg), 16):
            if DEBUG: print(f"SEND: Sending chunk {i // 16 + 1} with length {min(16, len(msg) - i)} bytes")
            self.send_and_wait(msg[i:i + 16])

    # -------------------------------------------------------------------------------------------------
    def recv_using_stop_and_wait(self, buff_size):
        """Retorna a lo mas `buff_size` bytes del mensaje en curso.

        Retorna apenas la cantidad de datos entregables alcanza
        min(largo_restante_del_mensaje, buff_size). Si un trozo recibido
        excede lo pedido, el sobrante se guarda en self.buffer y se entrega
        en la siguiente llamada, de modo que no se pierden datos y se puede
        llamar a recv() las veces que haga falta para recibir todo el mensaje.
        """
        if DEBUG: print(f"RECV: Receiving up to {buff_size} bytes")

        # Si no hay un mensaje en curso (nada por recibir de la red ni
        # sobrantes pendientes), el primer segmento trae el largo del mensaje.
        if self.remaining == 0 and not self.buffer:
            self.remaining = int.from_bytes(self.receive_and_confirm(), "big")
            if DEBUG: print(f"RECV: Starting new message reception with size {self.remaining} bytes")

        # Bytes del mensaje que aun no se entregan al llamador.
        pending = self.remaining + len(self.buffer)
        goal = min(pending, buff_size)

        # Recibimos segmentos hasta tener al menos `goal` bytes disponibles.
        while len(self.buffer) < goal:
            chunk = self.receive_and_confirm()
            self.buffer += chunk
            self.remaining -= len(chunk)
            if DEBUG: print(f"RECV: Received chunk of length {len(chunk)} bytes, remaining from net {self.remaining} bytes")

        out = self.buffer[:goal]
        self.buffer = self.buffer[goal:]

        if self.remaining == 0 and not self.buffer:
            if DEBUG: print("RECV: Message reception complete")
        return out

    # -------------------------------------------------------------------------------------------------
    # ----- Go-Back-N -----------------------------------------------------------------------------------
    # -------------------------------------------------------------------------------------------------
    def _debug_cc(self, event, window, window_size):
        """Imprime el estado del control de congestion y la ventana actual."""
        cc = self.congestion_controler
        estado = "slow_start" if cc.is_state_slow_start() else "congestion_avoidance"
        print(f"[CC/{event}] estado={estado} cwnd={cc.get_cwnd()} B "
              f"ssthresh={cc.get_ssthresh()} window_size={window_size} seg "
              f"(MSS_in_cwnd={cc.get_MSS_in_cwnd()})")
        print(window)

    # -------------------------------------------------------------------------------------------------
    def send_using_go_back_n(self, message):
        """Envía message usando Go-Back-N.

        El mensaje se divide en trozos de MSS bytes. El primer elemento enviado
        es el largo del mensaje (para que el receptor sepa cuánto esperar). Los
        números de secuencia se manejan por bytes, usando SlidingWindowCC. Si
        congestion_control_on == True el tamaño de la ventana lo define un
        objeto CongestionControl; si no, se usa una ventana fija.
        """
        MSS = self.MSS

        # data_list: [largo_del_mensaje] + trozos de MSS bytes.
        data_list = [str(len(message)).encode()]
        for i in range(0, len(message), MSS):
            data_list.append(message[i:i + MSS])
        total = len(data_list)

        # Números de secuencia por bytes (mismo criterio que SlidingWindowCC).
        initial_seq = self.seq
        seq_list = []
        acc = 0
        for element in data_list:
            seq_list.append(initial_seq + acc)
            acc += len(element)
        final_seq = initial_seq + acc

        # Tamaño de ventana inicial (en segmentos).
        if self.congestion_control_on:
            self.congestion_controler = CongestionControl(MSS)
            window_size = self.congestion_controler.get_MSS_in_cwnd()  # parte en 1
        else:
            window_size = self.GBN_WINDOW

        # Ventana deslizante (para mover/redimensionar y para el modo debug).
        window = SlidingWindowCC(window_size, list(data_list), initial_seq)

        # SocketUDP que adopta el socket ya conectado, para manejar el timer.
        udp = SocketUDP()
        udp.socket_udp.close()
        udp.socket_udp = self.socket
        self.socket.setblocking(False)
        udp.settimeout(self.GBN_TIMEOUT)

        if DEBUG: print(f"GBN_SEND: {total} segmentos (incluye largo), window_size={window_size}, cc={self.congestion_control_on}")
        if self.congestion_control_on and DEBUG_CC: self._debug_cc("inicio", window, window_size)

        acked_count = 0   # elementos confirmados desde el frente
        num_sent = 0      # elementos enviados al menos una vez

        def send_segment(index):
            segment = self.create_segment(0, seq_list[index], data_list[index])
            udp.sendto(segment, self.dest_addr, 0)
            self.number_of_sent_segments += 1
            if DEBUG: print(f"GBN_SEND: -> seq={seq_list[index]} ({len(data_list[index])} B)")

        def send_new_in_window():
            nonlocal num_sent
            end = min(acked_count + window_size, total)
            while num_sent < end:
                send_segment(num_sent)
                num_sent += 1

        def stop_timer():
            # Detiene el timer 0 solo si existe (evita error si ya fue detenido).
            if udp.timer_list[0] is not None:
                udp.stop_timer(0)

        # Envío inicial de la ventana.
        send_new_in_window()

        while acked_count < total:
            try:
                data, _ = udp.recvfrom(self.HEADER_SIZE + MSS)
            except TimeoutError:
                # Timeout: evento de control de congestión + reenvío Go-Back-N.
                if self.congestion_control_on:
                    self.congestion_controler.event_timeout()
                    new_ws = self.congestion_controler.get_MSS_in_cwnd()
                    if new_ws != window_size:
                        window.update_window_size(new_ws)
                        window_size = new_ws
                    if DEBUG_CC: self._debug_cc("timeout", window, window_size)
                elif DEBUG:
                    print("GBN_SEND: timeout, reenviando ventana")
                stop_timer()
                num_sent = acked_count          # volvemos a la base (Go-Back-N)
                send_new_in_window()
                continue

            flags, ack_seq, _ = self.parse_segment(data)
            if not flags & self.ACK:
                continue

            base_seq = seq_list[acked_count]
            if ack_seq > base_seq:
                # ACK acumulativo que confirma datos nuevos.
                new_acked = bisect.bisect_left(seq_list, ack_seq)
                steps = new_acked - acked_count
                # Movemos la ventana deslizante (incluye el caso borde en que el
                # ACK cae más allá de la ventana por haberse reducido su tamaño).
                remaining_steps = steps
                while remaining_steps > 0:
                    move = min(remaining_steps, window.window_size)
                    window.move_window(move)
                    remaining_steps -= move
                acked_count = new_acked

                if self.congestion_control_on:
                    self.congestion_controler.event_ack_received()
                    new_ws = self.congestion_controler.get_MSS_in_cwnd()
                    if new_ws != window_size:
                        window.update_window_size(new_ws)
                        window_size = new_ws
                    if DEBUG_CC: self._debug_cc("ack", window, window_size)

                stop_timer()
                if acked_count >= total:
                    break
                # Enviamos los k nuevos elementos que entraron a la ventana
                # (esto reinicia el timer). Si no hay nuevos pero quedan datos
                # sin confirmar, reenviamos la base para mantener vivo el timer.
                before = num_sent
                send_new_in_window()
                if num_sent == before:
                    send_segment(acked_count)
            # ACK duplicado: se ignora (solo slow start y congestion avoidance).

        stop_timer()
        self.socket.setblocking(True)
        self.socket.settimeout(None)
        self.seq = final_seq
        if DEBUG: print(f"GBN_SEND: envío completo. seq final={final_seq}, segmentos enviados (total)={self.number_of_sent_segments}")

    # -------------------------------------------------------------------------------------------------
    def recv_using_go_back_n(self, buff_size):
        """Recibe datos enviados con Go-Back-N respetando la semántica de
        buff_size (igual que en Stop & Wait): retorna a lo más buff_size bytes
        y guarda el sobrante para la siguiente llamada."""
        # Si no hay mensaje en curso, el primer segmento en orden trae el largo.
        if self.remaining == 0 and not self.buffer:
            self.remaining = int(self._gbn_receive_element().decode())
            if DEBUG: print(f"GBN_RECV: nuevo mensaje de {self.remaining} bytes")

        pending = self.remaining + len(self.buffer)
        goal = min(pending, buff_size)

        while len(self.buffer) < goal:
            chunk = self._gbn_receive_element()
            self.buffer += chunk
            self.remaining -= len(chunk)

        out = self.buffer[:goal]
        self.buffer = self.buffer[goal:]
        if self.remaining == 0 and not self.buffer:
            if DEBUG: print("GBN_RECV: mensaje recibido completo")
        return out

    # -------------------------------------------------------------------------------------------------
    def _gbn_receive_element(self):
        """Recibe el próximo segmento EN ORDEN, envía un ACK acumulativo con el
        siguiente byte esperado y retorna su payload. Ante segmentos fuera de
        orden o duplicados, reenvía el último ACK en orden (Go-Back-N)."""
        self.socket.settimeout(None)
        while True:
            data, addr = self.socket.recvfrom(self.HEADER_SIZE + self.MSS)
            flags, seq, payload = self.parse_segment(data)

            if addr == self.dest_addr and not (flags & self.FIN) and seq == self.seq:
                # Segmento en orden: avanzamos el byte esperado y confirmamos.
                self.seq += len(payload)
                self.last_ack_segment = self.create_segment(self.ACK, self.seq)
                self.socket.sendto(self.last_ack_segment, self.dest_addr)
                if DEBUG: print(f"GBN_RECV: en orden seq={seq} ({len(payload)} B), ACK acumulativo -> {self.seq}")
                return payload

            # Fuera de orden o duplicado: reconfirmamos el último byte en orden.
            self.last_ack_segment = self.create_segment(self.ACK, self.seq)
            self.socket.sendto(self.last_ack_segment, self.dest_addr)
            if DEBUG: print(f"GBN_RECV: segmento inesperado seq={seq}, reenvío ACK -> {self.seq}")

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
            except (socket.timeout, ConnectionResetError):
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
            except (socket.timeout, ConnectionResetError):
                if DEBUG: print("CLOSE: Timeout waiting for final ACK, assuming connection closed")
                break

        if DEBUG: print("CLOSE: Connection closed, cleaning up resources")
        self.clean()

    # -------------------------------------------------------------------------------------------------
    def recv_close(self):
        """Lado que recibe el cierre: espera FIN -> envía FIN+ACK -> espera ACK."""
        self.socket.settimeout(None)
        while True:
            try:
                data, addr = self.socket.recvfrom(20)
            except ConnectionResetError:
                continue
            flags, x, _ = self.parse_segment(data)
            if addr == self.dest_addr and flags & self.FIN and x == self.seq:
                if DEBUG: print(f"RECV_CLOSE: Received FIN with seq={x} from {addr}")
                break
            # Caso borde: se perdió el ACK del último segmento de datos. El
            # emisor retransmite datos mientras espera para poder cerrar.
            # Reenviamos el último ACK enviado por el receptor (sirve para
            # Stop & Wait y para Go-Back-N) para que su send() termine y pueda
            # enviarnos el FIN.
            if addr == self.dest_addr and not flags & self.FIN and self.last_ack_segment is not None:
                self.socket.sendto(self.last_ack_segment, self.dest_addr)
                if DEBUG: print(f"RECV_CLOSE: Re-confirmando dato retransmitido seq={x} (reenvío último ACK)")

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
            except (socket.timeout, ConnectionResetError):
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