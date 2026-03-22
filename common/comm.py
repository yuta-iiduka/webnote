""" 通信モジュール
TODO:中断や失敗した通信のバッファを削除する処理の実装
TODO:IPv6での検証(bindできていないはず)
"""

import asyncio
import json
import struct
import os
import uuid
import socket

INTERVAL_TIME = 0.001
MAX_PACKET_SIZE = 1024  # 分割サイズ
HEADER_FORMAT = "!I"    # 4byte length header
DUAL_STUCK_HOST = "::"
DUAL_STUCK_DEST = "::1"
LOCAL_HOST = "127.0.0.1"

class Packet:
    """ 
    パケットの生成クラス
    """
    def __init__(self, data: dict):
        self.data = data

    def encode(self):
        raw = json.dumps(self.data).encode()
        return struct.pack(HEADER_FORMAT, len(raw)) + raw

    @staticmethod
    async def read(reader: asyncio.StreamReader):
        header = await reader.readexactly(4)
        size = struct.unpack(HEADER_FORMAT, header)[0]
        body = await reader.readexactly(size)
        return json.loads(body.decode())


class PacketSplitter:
    """ 
    パケット分割処理クラス
    """
    @staticmethod
    def split(data: bytes):
        chunks = []
        total = len(data)
        packet_id = str(uuid.uuid4())

        for i in range(0, total, MAX_PACKET_SIZE):
            chunk = data[i:i + MAX_PACKET_SIZE]
            chunks.append({
                "type": "chunk",
                "id": packet_id,
                "index": i // MAX_PACKET_SIZE,
                "total": (total + MAX_PACKET_SIZE - 1) // MAX_PACKET_SIZE,
                "data": chunk.decode('latin1')
            })
        return chunks

class PacketAssembler:
    """ 
    パケット再構築クラス
    """
    def __init__(self):
        self.buffers = {}

    def add(self, packet):
        pid = packet["id"]

        if pid not in self.buffers:
            self.buffers[pid] = {
                "chunks": {},
                "total": packet["total"]
            }

        self.buffers[pid]["chunks"][packet["index"]] = packet["data"]

        if len(self.buffers[pid]["chunks"]) == self.buffers[pid]["total"]:
            data = "".join(
                self.buffers[pid]["chunks"][i]
                for i in range(self.buffers[pid]["total"])
            )
            del self.buffers[pid]
            return data.encode('latin1')
        return None

class FileAssembler:
    """ 
    ファイルパケット再構築クラス
    """
    def __init__(self):
        self.files = {}

    def add(self, packet):
        pid = packet["id"]
        filename = packet["filename"]

        if pid not in self.files:
            self.files[pid] = {
                "chunks": {},
                "total": packet["total"],
                "filename": filename
            }

        self.files[pid]["chunks"][packet["index"]] = packet["data"]

        # 全部揃ったら復元
        if len(self.files[pid]["chunks"]) == self.files[pid]["total"]:
            data = "".join(
                self.files[pid]["chunks"][i]
                for i in range(self.files[pid]["total"])
            ).encode("latin1")

            filename = self.files[pid]["filename"]
            del self.files[pid]

            return filename, data

        return None

# =========================
# 共通コネクションクラス
# =========================
class BaseConnection:
    def __init__(self):
        self._receive_callback = None
        self.assembler = PacketAssembler()
        self.file_assembler = FileAssembler()

    def get_address_family(self, host):
        try:
            # info = socket.getaddrinfo(host, None)[0]
            # return info[0]
            if ":" in host:
                return socket.AF_INET6
            else:
                return socket.AF_INET
        except:
            return socket.AF_INET

    def receive(self, callback):
        self._receive_callback = callback
        return callback

    def callback(self,func):
        try:
            method = getattr(self,func.__name__)
            if not method:
                setattr(self,func.__name__,func)

        except Exception as e:
            setattr(self,func.__name__,func)
        return func

    async def _handle_data(self, data, addr=None):
        if isinstance(data, dict) and data.get("type") == "chunk":
            assembled = self.assembler.add(data)
            if assembled:
                obj = json.loads(assembled.decode())

                try:
                    if isinstance(obj, dict) and obj.get("type", None):
                        method = getattr(self, obj["type"])
                        await method(obj,addr)
                except Exception as e:
                    print(e)

                if self._receive_callback:
                    await self._receive_callback(obj, addr)

        else:
            try:
                if isinstance(data, dict) and data.get("type", None):
                    method = getattr(self, data["type"])
                    await method(data,addr)
            except Exception as e:
                print(e)

            if self._receive_callback:
                await self._receive_callback(data, addr)

    async def file(self, data, addr):
        result = self.file_assembler.add(data)
        if result:
            filename, filedata = result
            # ファイル保存
            with open(f"{filename}", "wb") as f:
                f.write(filedata)


class TCPServer(BaseConnection):
    def __init__(self, host=DUAL_STUCK_HOST, port=9999):
        super().__init__()
        self.host = host
        self.port = port
        self.clients = set()
        self.family = self.get_address_family(host)

    async def run(self):
        server = await asyncio.start_server(self._handle_client, self.host, self.port, family=self.family)
        async with server:
            await server.serve_forever()

    async def _handle_client(self, reader, writer):
        addr = writer.get_extra_info("peername")
        self.clients.add(writer)

        try:
            while True:
                data = await Packet.read(reader)
                await self._handle_data(data, addr)
        except:
            pass
        finally:
            self.clients.remove(writer)
            writer.close()
            await writer.wait_closed()

    async def send(self, data):
        raw = json.dumps(data).encode()
        if len(raw) > MAX_PACKET_SIZE:
            chunks = PacketSplitter.split(raw)
            for chunk in chunks:
                await self._broadcast(chunk)
                await asyncio.sleep(INTERVAL_TIME)
        else:
            await self._broadcast(data)

    async def _broadcast(self, data):
        packet = Packet(data).encode()
        for client in self.clients:
            client.write(packet)
            await client.drain()
            await asyncio.sleep(INTERVAL_TIME)

    async def sendto(self, addr, data):
        for client in self.clients:
            if client.get_extra_info("peername") == addr:
                packet = Packet(data).encode()
                client.write(packet)
                await client.drain()
                await asyncio.sleep(INTERVAL_TIME)

    async def sendfile(self, addr, filename, filedata):
        chunks = PacketSplitter.split(filedata)
        for chunk in chunks:
            chunk["type"] = "file"
            chunk["filename"] = filename
            await self.sendto(addr, chunk)
            await asyncio.sleep(INTERVAL_TIME)

class TCPClient(BaseConnection):
    def __init__(self, host=DUAL_STUCK_DEST, port=9999, local_port=9999):
        super().__init__()
        self.host = host
        self.port = port
        self.local_port = local_port
        self.reader = None
        self.writer = None
        self.family = self.get_address_family(host)

    async def run(self):
        loop = asyncio.get_running_loop()
        # sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock = socket.socket(self.family, socket.SOCK_STREAM)
        if self.local_port:
            if ":" in self.host:
                sock.bind((LOCAL_HOST, self.local_port))
            else:
                sock.bind(("::", self.local_port))

        sock.setblocking(False)
        await loop.sock_connect(sock, (self.host, self.port))
        self.reader, self.writer = await asyncio.open_connection(sock=sock)
        asyncio.create_task(self._listen())

    async def _listen(self):
        while True:
            data = await Packet.read(self.reader)
            await self._handle_data(data)

    async def send(self, data):
        raw = json.dumps(data).encode()
        if len(raw) > MAX_PACKET_SIZE:
            chunks = PacketSplitter.split(raw)
            for chunk in chunks:
                await self._send(chunk)
                await asyncio.sleep(INTERVAL_TIME)
        else:
            await self._send(data)

    async def _send(self, data):
        packet = Packet(data).encode()
        self.writer.write(packet)
        await self.writer.drain()

    async def sendto(self, addr, data):
        await self.send(data)

    async def sendfile(self, addr, filename, filedata):
        chunks = PacketSplitter.split(filedata)
        for chunk in chunks:
            chunk["type"] = "file"
            chunk["filename"] = filename
            await self.send(chunk)
            await asyncio.sleep(INTERVAL_TIME)

class UDPServer(BaseConnection):
    def __init__(self, host=DUAL_STUCK_HOST, port=9999):
        super().__init__()
        self.host = host
        self.port = port
        self.transport = None
        self.family = self.get_address_family(host)

    async def run(self):
        loop = asyncio.get_running_loop()
        await loop.create_datagram_endpoint(
            lambda: self,
            local_addr=(self.host, self.port),
            family=self.family,
        )

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        obj = json.loads(data.decode())
        asyncio.create_task(self._handle_data(obj, addr))

    async def send(self, data):
        raw = json.dumps(data).encode()
        if len(raw) > MAX_PACKET_SIZE:
            chunks = PacketSplitter.split(raw)
            for chunk in chunks:
                self.transport.sendto(json.dumps(chunk).encode())
                await asyncio.sleep(INTERVAL_TIME)

        else:
            self.transport.sendto(raw)

    async def sendto(self, addr, data):
        raw = json.dumps(data).encode()
        self.transport.sendto(raw, addr)

    async def sendfile(self, addr, filename, filedata):
        chunks = PacketSplitter.split(filedata)
        for chunk in chunks:
            chunk["type"] = "file"
            chunk["filename"] = filename
            await self.sendto(addr, chunk)
            await asyncio.sleep(INTERVAL_TIME)

    def pause_writing(self):
        print("送信一時停止（バッファ満杯）")

    def resume_writing(self):
        print("送信再開")

class UDPClient(BaseConnection):
    def __init__(self, host=DUAL_STUCK_DEST, port=9999, local_port=9999):
        super().__init__()
        self.host = host
        self.port = port
        self.local_port = local_port
        self.transport = None
        self.family = self.get_address_family(host)

    async def run(self):
        loop = asyncio.get_running_loop()
        local_addr = None
        if self.local_port:
            local_addr = (LOCAL_HOST, self.local_port)

        await loop.create_datagram_endpoint(
            lambda: self,
            local_addr=local_addr,
            remote_addr=(self.host, self.port),
            family=self.family,
        )

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        obj = json.loads(data.decode())
        asyncio.create_task(self._handle_data(obj, addr))

    async def send(self, data):
        raw = json.dumps(data).encode()
        if len(raw) > MAX_PACKET_SIZE:
            chunks = PacketSplitter.split(raw)
            for chunk in chunks:
                self.transport.sendto(json.dumps(chunk).encode())
                await asyncio.sleep(INTERVAL_TIME)
        else:
            self.transport.sendto(raw)

    async def sendto(self, addr, data):
        self.transport.sendto(json.dumps(data).encode(), addr)

    async def sendfile(self, addr, filename, filedata):
        chunks = PacketSplitter.split(filedata)
        for chunk in chunks:
            chunk["type"] = "file"
            chunk["filename"] = filename
            await self.sendto(addr,chunk)
            await asyncio.sleep(INTERVAL_TIME)

    def pause_writing(self):
        print("送信一時停止（バッファ満杯）")

    def resume_writing(self):
        print("送信再開")


async def run_server():
    server = TCPServer(host=LOCAL_HOST, port=9999)
    # server = UDPServer(host=LOCAL_HOST, port=9999)

    # 受信時の処理（コールバック）
    @server.receive
    async def on_receive(data, addr):
        print(f"[SERVER] 受信 from {addr}: {data}")
        # await server.sendto((LOCAL_HOST, 9998),{"type":"chat","message":"OK"})

    print("Server 起動")
    await server.run()

    try:
        while True:
            await asyncio.sleep(3600)

    except KeyboardInterrupt:
        print("Server 停止")
        

async def run_client():
    client = TCPClient(LOCAL_HOST, 9999, 9998)
    # client = UDPClient(LOCAL_HOST, 9999, 9998)

    @client.receive
    async def on_receive(data, addr):
        print(f"[CLIENT] 受信: {addr}: {data}")
        

    await client.run()
    # 少し待ってから送信
    await asyncio.sleep(1)
    await client.sendto((LOCAL_HOST, 9999),{
        "type": "chat",
        "message": "Hello Server!"
    })

    # with open("etc/data/sample.pptx","rb") as f:
    #     data = f.read()

    await asyncio.gather(
        # client.sendfile((LOCAL_HOST, 9999), "sample1.pptx", data),
        # client.sendfile((LOCAL_HOST, 9999), "sample2.pptx", data),
        client.sendto((LOCAL_HOST,9999), {"type":"chat","message":"HELLO", "list":[]})
    )

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("Client 停止")


async def main():
    await asyncio.gather(
        run_server(),
        run_client(),
    )


if __name__ == "__main__":
    asyncio.run(main())
