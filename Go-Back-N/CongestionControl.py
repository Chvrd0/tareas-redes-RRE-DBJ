DEBUG = False

class CongestionControl:
    # -------------------------------------------------------------------------------------------------
    # ------ Constantes -------------------------------------------------------------------------------
    # -------------------------------------------------------------------------------------------------
    SLOW_START = "slow_start"
    CONGESTION_AVOIDANCE = "congestion_avoidance"

    # -------------------------------------------------------------------------------------------------
    # ----- Constructor -------------------------------------------------------------------------------
    # -------------------------------------------------------------------------------------------------
    def __init__(self, MSS):
        # Estado actual: siempre parte en slow start.
        self.current_state = self.SLOW_START
        # Tamaño maximo del area de datos de un segmento (en bytes).
        self.MSS = MSS
        # Ventana de congestion en bytes. Parte en 1 MSS.
        self.cwnd = MSS
        # Slow Start threshold. Indefinido hasta el primer timeout.
        self.ssthresh = None
        if DEBUG: print(f"CC: nuevo CongestionControl MSS={MSS}, cwnd={self.cwnd}, estado={self.current_state}")

    # -------------------------------------------------------------------------------------------------
    # ----- Getters -----------------------------------------------------------------------------------
    # -------------------------------------------------------------------------------------------------
    def get_cwnd(self):
        """Retorna el tamaño de la ventana de congestion en bytes."""
        return self.cwnd

    # -------------------------------------------------------------------------------------------------
    def get_MSS_in_cwnd(self):
        """Retorna cuantos MSS completos caben en la cwnd actual."""
        return int(self.cwnd // self.MSS)

    # -------------------------------------------------------------------------------------------------
    def get_ssthresh(self):
        """Retorna el valor actual de ssthresh (None si aun no se define)."""
        return self.ssthresh

    # -------------------------------------------------------------------------------------------------
    def is_state_slow_start(self):
        return self.current_state == self.SLOW_START

    # -------------------------------------------------------------------------------------------------
    def is_state_congestion_avoidance(self):
        return self.current_state == self.CONGESTION_AVOIDANCE

    # -------------------------------------------------------------------------------------------------
    # ----- Eventos de control de congestion ----------------------------------------------------------
    # -------------------------------------------------------------------------------------------------
    def event_ack_received(self):
        """Maneja la recepcion exitosa de un ACK.

        - slow start: aumenta la cwnd en 1 MSS por cada ACK.
        - congestion avoidance (AIMD): aumenta la cwnd en una fraccion
          (1 / get_MSS_in_cwnd()) de MSS por cada ACK, de modo que tras
          recibir tantos ACKs como MSS caben en la ventana la cwnd crece 1 MSS.
        """
        if self.is_state_slow_start():
            self.cwnd += self.MSS
            if DEBUG: print(f"CC: ACK en slow start -> cwnd={self.cwnd}")
            # Si alcanzamos el umbral, pasamos a congestion avoidance.
            if self.ssthresh is not None and self.cwnd >= self.ssthresh:
                self.current_state = self.CONGESTION_AVOIDANCE
                if DEBUG: print(f"CC: cwnd>=ssthresh ({self.ssthresh}) -> cambio a congestion avoidance")

        elif self.is_state_congestion_avoidance():
            self.cwnd += self.MSS * (1 / self.get_MSS_in_cwnd())
            if DEBUG: print(f"CC: ACK en congestion avoidance -> cwnd={self.cwnd}")

    # -------------------------------------------------------------------------------------------------
    def event_timeout(self):
        """Maneja la ocurrencia de un timeout (perdida).

        En TCP Tahoe, ante timeout se define ssthresh = cwnd/2, se reinicia
        la cwnd a 1 MSS y se vuelve a slow start. La primera vez que ocurre
        esto es donde se inicializa ssthresh (antes era None).
        """
        self.ssthresh = int(self.cwnd / 2)
        self.cwnd = self.MSS
        self.current_state = self.SLOW_START
        if DEBUG: print(f"CC: timeout -> ssthresh={self.ssthresh}, cwnd={self.cwnd}, estado={self.current_state}")
