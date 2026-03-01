"""
通信モジュール
"""

import socket,threading,asyncio,json,struct,time


# TODO:受信データの管理はどうするか？
# TODO:ipv6の対応

class Communication:

    CHUNK_SIZE = 1024
    TIME_OUT = 5.0


    def __init__(self,host="127.0.0.1",port=9999):
        self.host = host
        self.port = port
        self.status = 0 # 開始：０、終了：１

    def encode(self,data):
        return json.dumps(data).encode()
    
    def decode(self,txt='{message:""}'):
        return json.loads(txt.decode())
    
    def open(self):
        pass

    def close(self):
        pass

class TCPServer(Communication):

    cnt = 0

    def __init__(self,host="127.0.0.1",port=9999):
        super().__init__(host,port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((host,port))
        self.socket.listen()
        print("TCP待機中・・・")

    def join(self):
        thread = threading.Thread(target=open)
        TCPServer.cnt += 1
        thread.name = f"tcp-client-{TCPServer.cnt}"
        thread.start()
    
    def open(self):
        try:
            while True:
                conn, addr = self.socket.accept()
                print("接続：", addr)
                if self.status == 1:
                    raise Exception("このコネクションはクローズしています。")
                data = conn.recv(1024)
                if data:
                    print(f"受信：{addr[0]}:{addr[1]}：{data}")
                    self.data = self.decode(data)
                    conn.sendall(self.encode({"message":"OK"}))
                else:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n終了します")
        except Exception as e:
            print(e)
            conn.sendall(self.encode({"error":"NG"}))
        finally:
            conn.close()

    def close(self):
        self.status = 1
        self.socket.close()

class TCPClient(Communication):
    def __init__(self,host="127.0.0.1",port=9999):
        super().__init__(host,port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(Communication.TIME_OUT)
        self.socket.connect((host, port))

    def close(self):
        self.status = 1
        self.socket.close()

    def send(self,msg={"message":"HELLO"}):
        self.socket.sendall(self.encode(msg))
        data, addr = self.socket.recvfrom(1024)
        self.data = self.decode(data)
        print(f"受信：{data}")
        self.socket.close()

class UDPServer(Communication):
    def __init__(self,host="127.0.0.1",port=9999):
        super().__init__(host,port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host,port))
        print("UDP待機中・・・")

    def open(self):
        try:
            while True:
                try:
                    data, addr = self.socket.recvfrom(1024)
                    if data:
                        print(f"受信：{addr[0]}:{addr[1]}：{data}")
                        self.socket.sendto(self.encode({"message":"OK"}),addr)
                        if self.status == 1:
                            raise Exception("このコネクションはクローズしています。")
                    else:
                        time.sleep(0.1)
                except Exception as e:
                    print(e)
                    self.socket.sendto(self.encode({"error":"NG"}),addr)

        except KeyboardInterrupt:
            print("\n終了します")

    def close(self):
        self.status = 1

class UDPClient(Communication):
    def __init__(self,host="127.0.0.1",port=9999):
        super().__init__(host,port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(Communication.TIME_OUT)

    def close(self):
        self.status = 1

    def send(self,msg={"message":"HELLO"}):
        self.socket.sendto(self.encode(msg),(self.host,self.port))
        try:
            if self.status == 1:
                raise Exception("このコネクションはクローズしています。")
            data,addr = self.socket.recvfrom(1024)
            self.data = self.decode(data)
            print(f"受信：{data}")
            print(self.data)
        except socket.timeout:
            print("タイムアウトしました。")
        except Exception as e:
            print(e)

class AsyncTCPServer(Communication):

    @classmethod
    async def run(cls,host="127.0.0.1",port=9999):
        self = cls(host,port)
        await self.open()
        return self

    def __init__(self,host="127.0.0.1",port=9999):
        super().__init__(host,port)
        print("TCP待機中・・・")

    async def handler(self,reader,writer):
        self.writer = writer
        self.reader = reader
        addr = writer.get_extra_info("peername")
        while True:
            data = await reader.read(Communication.CHUNK_SIZE)
            if not data:
                break
            self.data = self.decode(data)
            print(self.data)
            writer.write(self.encode({"message":"OK"}))
            await writer.drain()
        self.close()
    
    async def open(self):
        self.server = await asyncio.start_server(self.handler, self.host, self.port)
        addr = self.server.sockets[0].getsockname()
        async with self.server:
            await self.server.serve_forever()

    async def close(self):
        self.status = 1
        self.writer.close()
        await self.writer.wait_closed()

    async def send(self,data={"message":""}):
        self.writer.write(self.encode(data))
        await self.writer.drain()
        chunks = []
        while True:
            chunk = await self.reader.read(Communication.CHUNK_SIZE)
            if not chunk:
                break
            chunks.append(chunk)
        self.data = self.decode(b"".join(chunks))
        print(self.data)

class AsyncTCPClient(Communication):

    @classmethod
    async def run(cls,host="127.0.0.1",port=9999):
        self = cls(host,port)
        await self.open()
        return self

    def __init__(self,host="127.0.0.1",port=9999):
        super().__init__(host,port)

    async def open(self):
        self.reader, self.writer = await asyncio.open_connection(self.host,self.port)
        await self.send({"message":"HELLO"})

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()

    async def send(self,data={"message":""}):
        self.writer.write(self.encode(data))
        await self.writer.drain()
        chunks = []
        while True:
            chunk = await self.reader.read(Communication.CHUNK_SIZE)
            if not chunk:
                break
            chunks.append(chunk)
            print(chunks)
        self.data = self.decode(b"".join(chunks))
        print(self.data)
        await self.close()


if __name__ == "__main__":
    pass
