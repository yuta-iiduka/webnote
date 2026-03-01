from common.comm import *

if __name__ == "__main__":
    # udp = UDPClient()
    # udp.send()

    # tcp = TCPClient()
    # tcp.send()

    tcp = AsyncTCPClient()
    asyncio.run(tcp.open())