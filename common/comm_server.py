from common.comm import *

if __name__ == "__main__":
    # udp = UDPServer()
    # udp.open()

    # tcp = TCPServer()
    # tcp.open()

    tcp = AsyncTCPServer()
    asyncio.run(tcp.open())