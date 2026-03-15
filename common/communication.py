import socket
import selectors
import threading
import struct
import pickle
import uuid
import time
from concurrent.futures import ThreadPoolExecutor

HEADER_SIZE = 4
MAX_PACKET = 65507


class BaseTransport:

    def __init__(self):
        self.selector = selectors.DefaultSelector()
        self.callback = None
        self.executor = ThreadPoolExecutor(max_workers=8)
        self.running = False

    def receive(self, callback):
        self.callback = callback

    def _dispatch(self, data, addr):
        if self.callback:
            self.executor.submit(self.callback, data, addr)

    def _encode(self, data):
        payload = pickle.dumps(data)
        size = struct.pack(">I", len(payload))
        return size + payload

    def _decode_stream(self, buffer):

        messages = []

        while True:
            if len(buffer) < HEADER_SIZE:
                break

            size = struct.unpack(">I", buffer[:HEADER_SIZE])[0]

            if len(buffer) < HEADER_SIZE + size:
                break

            payload = buffer[HEADER_SIZE:HEADER_SIZE + size]
            buffer = buffer[HEADER_SIZE + size:]

            messages.append(pickle.loads(payload))

        return messages, buffer
    
class TCPServer(BaseTransport):

    def __init__(self, host="0.0.0.0", port=9000):
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

        self.clients[conn] = {"addr": addr, "buffer": b""}

        self.selector.register(conn, selectors.EVENT_READ, self._read)

    def _read(self, conn):

        try:
            data = conn.recv(4096)

            if not data:
                self.selector.unregister(conn)
                conn.close()
                return

            client = self.clients[conn]
            client["buffer"] += data

            messages, client["buffer"] = self._decode_stream(client["buffer"])

            for msg in messages:
                self._dispatch(msg, client["addr"])

        except:
            pass

    def send(self, conn, data):
        packet = self._encode(data)
        conn.sendall(packet)

    def sendto(self, addr, data):
        for conn, info in self.clients.items():
            if info["addr"] == addr:
                self.send(conn, data)

    def run(self):

        self.running = True

        while self.running:
            events = self.selector.select()

            for key, _ in events:
                callback = key.data
                callback(key.fileobj)

class TCPClient(BaseTransport):

    def __init__(self,host="0.0.0.0", port=9000):
        super().__init__()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.sock.setblocking(False)

        self.buffer = b""

        self.selector.register(self.sock, selectors.EVENT_READ, self._read)

    def _read(self, sock):

        data = sock.recv(4096)

        self.buffer += data

        messages, self.buffer = self._decode_stream(self.buffer)

        for m in messages:
            self._dispatch(m, sock.getpeername())

    def send(self, data):
        packet = self._encode(data)
        self.sock.sendall(packet)

    def sendto(self, addr, data):
        self.send(data)

    def run(self):

        self.running = True

        while self.running:
            events = self.selector.select()

            for key, _ in events:
                callback = key.data
                callback(key.fileobj)

class UDPServer(BaseTransport):

    def __init__(self, host="0.0.0.0", port=9000):
        super().__init__()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.setblocking(False)

        self.selector.register(self.sock, selectors.EVENT_READ, self._read)

    def _read(self, sock):

        data, addr = sock.recvfrom(MAX_PACKET)

        msg = pickle.loads(data)

        self._dispatch(msg, addr)

    def send(self, data):
        pass

    def sendto(self, addr, data):

        payload = pickle.dumps(data)

        if len(payload) > MAX_PACKET:
            raise ValueError("UDP packet too large")

        self.sock.sendto(payload, addr)

    def run(self):

        self.running = True

        while self.running:

            events = self.selector.select()

            for key, _ in events:
                callback = key.data
                callback(key.fileobj)

class UDPClient(BaseTransport):

    def __init__(self, host="0.0.0.0", port=9000):
        super().__init__()

        self.server = (host, port)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)

        self.selector.register(self.sock, selectors.EVENT_READ, self._read)

    def _read(self, sock):

        data, addr = sock.recvfrom(MAX_PACKET)

        msg = pickle.loads(data)

        self._dispatch(msg, addr)

    def send(self, data):

        payload = pickle.dumps(data)

        self.sock.sendto(payload, self.server)

    def sendto(self, addr, data):

        payload = pickle.dumps(data)

        self.sock.sendto(payload, addr)

    def run(self):

        self.running = True

        while self.running:

            events = self.selector.select()

            for key, _ in events:
                callback = key.data
                callback(key.fileobj)


class Session:

    def __init__(self, conn=None, addr=None, transport=None):

        self.id = str(uuid.uuid4())
        self.conn = conn
        self.addr = addr
        self.transport = transport

        self.created_at = time.time()
        self.updated_at = self.created_at

        self.data = {}

    def send(self, data):

        if self.transport:
            self.transport.send(data)

        elif self.conn:
            raise RuntimeError("transport未設定")


class SessionManager:

    def __init__(self):

        self.sessions = {}
        self.conn_index = {}
        self.addr_index = {}

        self.lock = threading.RLock()

    # CREATE
    def create(self, conn=None, addr=None, transport=None):

        session = Session(conn, addr, transport)

        with self.lock:

            self.sessions[session.id] = session

            if conn:
                self.conn_index[conn] = session.id

            if addr:
                self.addr_index[addr] = session.id

        return session

    # READ
    def get(self, session_id):

        with self.lock:
            return self.sessions.get(session_id)

    def get_by_conn(self, conn):

        with self.lock:
            sid = self.conn_index.get(conn)

            if sid:
                return self.sessions.get(sid)

    def get_by_addr(self, addr):

        with self.lock:
            sid = self.addr_index.get(addr)

            if sid:
                return self.sessions.get(sid)

    # UPDATE
    def update(self, session_id, **kwargs):

        with self.lock:

            session = self.sessions.get(session_id)

            if not session:
                return None

            for k, v in kwargs.items():
                setattr(session, k, v)

            session.updated_at = time.time()

            return session

    # DELETE
    def delete(self, session_id):

        with self.lock:

            session = self.sessions.pop(session_id, None)

            if not session:
                return False

            if session.conn in self.conn_index:
                del self.conn_index[session.conn]

            if session.addr in self.addr_index:
                del self.addr_index[session.addr]

            return True

    # LIST
    def list_sessions(self):

        with self.lock:
            return list(self.sessions.values())

    # COUNT
    def count(self):

        with self.lock:
            return len(self.sessions)

    # BROADCAST
    def broadcast(self, data):

        with self.lock:

            for session in self.sessions.values():

                try:
                    session.send(data)
                except Exception:
                    pass

    # MULTICAST
    def multicast(self, session_ids, data):

        with self.lock:

            for sid in session_ids:

                session = self.sessions.get(sid)

                if session:
                    try:
                        session.send(data)
                    except Exception:
                        pass

if __name__ == "__main__":

    server = TCPServer("127.0.0.1",port=9000)

    def on_receive(data, addr):
        print("recv", addr, data)

    server.receive(on_receive)

    server_thread = threading.Thread(target=server.run).start()


    client = TCPClient("127.0.0.1", 9000)

    def on_receive(data, addr):
        print("server:", data)

    client.receive(on_receive)

    client_thread = threading.Thread(target=client.run).start()

    client.send({"msg":"hello"})




