import socket
import selectors
import json
import uuid
import struct
from abc import ABC, abstractmethod

MAX_PACKET = 1024


class PacketCodec:

    def __init__(self):
        self.buffers = {}

    def encode_packets(self, data):

        payload = json.dumps(data).encode()

        chunks = [
            payload[i:i + MAX_PACKET]
            for i in range(0, len(payload), MAX_PACKET)
        ]

        total = len(chunks)
        msg_id = str(uuid.uuid4())

        packets = []

        for i, chunk in enumerate(chunks):

            packet = {
                "id": msg_id,
                "index": i,
                "total": total,
                "data": chunk.decode()
            }

            raw = json.dumps(packet).encode()

            header = struct.pack("!I", len(raw))

            packets.append(header + raw)

        return packets

    def decode_stream(self, conn, data):

        if conn not in self.buffers:
            self.buffers[conn] = b""

        self.buffers[conn] += data

        messages = []

        while True:

            if len(self.buffers[conn]) < 4:
                break

            length = struct.unpack("!I", self.buffers[conn][:4])[0]

            if len(self.buffers[conn]) < 4 + length:
                break

            payload = self.buffers[conn][4:4 + length]

            self.buffers[conn] = self.buffers[conn][4 + length:]

            packet = json.loads(payload.decode())

            messages.append(packet)

        return messages


class PacketAssembler:

    def __init__(self):
        self.storage = {}

    def add(self, packet):

        msg_id = packet["id"]
        idx = packet["index"]
        total = packet["total"]
        data = packet["data"]

        if msg_id not in self.storage:
            self.storage[msg_id] = {
                "total": total,
                "chunks": {}
            }

        self.storage[msg_id]["chunks"][idx] = data

        if len(self.storage[msg_id]["chunks"]) == total:

            chunks = self.storage[msg_id]["chunks"]

            full = "".join(
                chunks[i] for i in range(total)
            )

            del self.storage[msg_id]

            return json.loads(full)

        return None


class BaseConnection(ABC):

    def __init__(self):

        self.selector = selectors.DefaultSelector()
        self.codec = PacketCodec()
        self.assembler = PacketAssembler()

        self.recv_callback = None

    def receive(self, callback):

        self.recv_callback = callback

    @abstractmethod
    def send(self, data):
        pass

    @abstractmethod
    def sendto(self, addr, data):
        pass

    @abstractmethod
    def run(self):
        pass


class TCPServer(BaseConnection):

    def __init__(self, host, port):

        super().__init__()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.sock.bind((host, port))
        self.sock.listen()

        self.sock.setblocking(False)

        self.selector.register(self.sock, selectors.EVENT_READ, self._accept)

        self.clients = {}

    def _accept(self, sock):

        conn, addr = sock.accept()
        conn.setblocking(False)

        self.clients[conn] = addr

        self.selector.register(conn, selectors.EVENT_READ, self._read)

    def _read(self, conn):

        try:
            data = conn.recv(4096)
        except:
            data = None

        if not data:
            self.selector.unregister(conn)
            conn.close()
            del self.clients[conn]
            return

        packets = self.codec.decode_stream(conn, data)

        for packet in packets:

            msg = self.assembler.add(packet)

            if msg and self.recv_callback:
                self.recv_callback(self.clients[conn], msg)

    def send(self, data):

        packets = self.codec.encode_packets(data)

        for conn in list(self.clients):

            try:
                for p in packets:
                    conn.sendall(p)
            except:
                pass

    def sendto(self, addr, data):

        packets = self.codec.encode_packets(data)
        for conn, a in self.clients.items():
            if a == addr:
                try:
                    for p in packets:
                        conn.sendall(p)
                except:
                    pass

    def run(self):

        while True:

            events = self.selector.select()

            for key, _ in events:

                callback = key.data
                callback(key.fileobj)


class TCPClient(BaseConnection):

    def __init__(self, host, port):

        super().__init__()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.sock.connect((host, port))

        self.sock.setblocking(False)

        self.selector.register(self.sock, selectors.EVENT_READ, self._read)

    def _read(self, sock):

        try:
            data = sock.recv(4096)
        except:
            data = None

        if not data:
            return

        packets = self.codec.decode_stream(sock, data)

        for packet in packets:

            msg = self.assembler.add(packet)

            if msg and self.recv_callback:
                self.recv_callback(msg)

    def send(self, data):

        packets = self.codec.encode_packets(data)

        for p in packets:
            self.sock.sendall(p)

    def sendto(self, addr, data):

        self.send(data)

    def run(self):

        while True:

            events = self.selector.select()

            for key, _ in events:

                callback = key.data
                callback(key.fileobj)


class UDPServer(BaseConnection):

    def __init__(self, host, port):

        super().__init__()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.sock.bind((host, port))

        self.sock.setblocking(False)

        self.selector.register(self.sock, selectors.EVENT_READ, self._read)

    def _read(self, sock):

        data, addr = sock.recvfrom(65535)

        try:
            packet = json.loads(data.decode())
        except:
            return

        msg = self.assembler.add(packet)

        if msg and self.recv_callback:
            self.recv_callback(addr, msg)

    def send(self, data):
        pass

    def sendto(self, addr, data):

        packets = self.codec.encode_packets(data)

        for p in packets:

            raw = p[4:]

            self.sock.sendto(raw, addr)

    def run(self):

        while True:

            events = self.selector.select()

            for key, _ in events:

                callback = key.data
                callback(key.fileobj)


class UDPClient(BaseConnection):

    def __init__(self):

        super().__init__()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.sock.setblocking(False)

        self.selector.register(self.sock, selectors.EVENT_READ, self._read)

    def _read(self, sock):

        data, addr = sock.recvfrom(65535)

        try:
            packet = json.loads(data.decode())
        except:
            return

        msg = self.assembler.add(packet)

        if msg and self.recv_callback:
            self.recv_callback(addr, msg)

    def send(self, data):
        pass

    def sendto(self, addr, data):

        packets = self.codec.encode_packets(data)

        for p in packets:

            raw = p[4:]

            self.sock.sendto(raw, addr)

    def run(self):

        while True:

            events = self.selector.select()

            for key, _ in events:

                callback = key.data
                callback(key.fileobj)

