"""DTU-Pro-S Modbus 2023 : limitation temporaire, aucune écriture permanente."""
import socket
import struct
import time
from contextlib import nullcontext

class DtuControl:
    def __init__(self, host, ports=4, rated_w=2000, lock=None):
        self.host, self.ports, self.rated_w = host, ports, rated_w
        self.lock = lock
        self.last_command = None

    def transaction(self, function, address, value):
        with (self.lock or nullcontext()):
            with socket.create_connection((self.host, 502), timeout=3) as sock:
                sock.settimeout(3)
                sock.sendall(struct.pack('>HHHBBHH', 17, 0, 6, 1, function, address, value))
                def receive(n):
                    result = b''
                    while len(result) < n:
                        part = sock.recv(n-len(result))
                        if not part:
                            raise ConnectionError('Réponse Modbus incomplète')
                        result += part
                    return result
                header = receive(7)
                transaction, protocol, length, unit = struct.unpack('>HHHB', header)
                if transaction != 17 or protocol != 0 or unit != 1 or not 2 <= length <= 254:
                    raise ValueError('En-tête Modbus invalide')
                data = receive(length-1)
                if data[0] != function:
                    raise ValueError('Commande Modbus refusée')
                if function == 6:
                    if data != struct.pack('>BHH', function, address, value):
                        raise ValueError('Accusé Modbus incorrect')
                    return
                if len(data) != 2 + value*2 or data[1] != value*2:
                    raise ValueError('Nombre de registres incorrect')
                return list(struct.unpack('>'+'H'*value, data[2:]))

    def snapshot(self):
        with (self.lock or nullcontext()):
            try:
                if self.transaction(4, 0x3004, 1) != [1]:
                    raise ValueError('Nombre de micro-onduleurs DTU inattendu')
                data = self.transaction(3, 0xD006, self.ports*6)
                limits = [data[i*6+1] for i in range(self.ports)]
                if any(data[i*6] != 1 for i in range(self.ports)) or not all(2 <= n <= 100 for n in limits):
                    raise ValueError('Ports DTU arrêtés ou limites invalides')
                power = self.transaction(4, 0x3108, 2)
                state = dict(state='online', timestamp=time.time(), power_w=((power[0]<<16)|power[1])/10,
                             limit_pct=min(limits), port_limits_pct=limits, rated_w=self.rated_w)
                if self.last_command is not None:
                    state.update(last_command_pct=self.last_command,
                                 last_command_confirmed=all(n == self.last_command for n in limits))
                return state
            except Exception as exc:
                return dict(state='offline', reason=type(exc).__name__)

    def request_limit(self, percent, snapshot):
        with (self.lock or nullcontext()):
            if isinstance(percent, bool) or not isinstance(percent, int) or not 2 <= percent <= 100:
                raise ValueError('Limite DTU hors plage')
            if snapshot.get('state') == 'online' and snapshot.get('port_limits_pct') == [percent]*self.ports:
                return
            self.transaction(6, 0xD001, percent)
            self.last_command = percent
