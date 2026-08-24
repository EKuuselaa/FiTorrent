import asyncio
import struct

PROTOCOL = b'BitTorrent protocol'

# Message IDs
CHOKE = 0
UNCHOKE = 1
INTERESTED = 2
NOT_INTERESTED = 3
HAVE = 4
BITFIELD = 5
REQUEST = 6
PIECE = 7
CANCEL = 8

BLOCK_SIZE = 2 ** 14


class PeerConnection:
    def __init__(self, ip, port, info_hash, peer_id):
        self.ip = ip
        self.port = port
        self.info_hash = info_hash
        self.peer_id = peer_id

        self.reader = None
        self.writer = None

        self.choked = True
        self.interested = False
        self.peer_choked = True
        self.peer_interested = False
        self.bitfield = None

    async def connect(self, timeout=10):
        """Open the TCP connection and perform the handshake"""
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(self.ip, self.port), timeout
        )
        await self._handshake()

    async def _handshake(self):
        message = (
            bytes([len(PROTOCOL)])
            + PROTOCOL
            + bytes(8)
            + self.info_hash
            + self.peer_id
        )
        self.writer.write(message)
        await self.writer.drain()

        response = await self.reader.readexactly(len(message))
        pstrlen = response[0]
        recv_info_hash = response[1 + pstrlen + 8:1 + pstrlen + 8 + 20]
        if recv_info_hash != self.info_hash:
            raise ConnectionError('info_hash mismatch during handshake')

        return response

    async def send_interested(self):
        await self._send_message(INTERESTED)
        self.interested = True

    async def send_not_interested(self):
        await self._send_message(NOT_INTERESTED)
        self.interested = False

    async def send_request(self, index, begin, length=BLOCK_SIZE):
        payload = struct.pack('>III', index, begin, length)
        await self._send_message(REQUEST, payload)

    async def send_have(self, index):
        payload = struct.pack('>I', index)
        await self._send_message(HAVE, payload)

    async def _send_message(self, message_id, payload=b''):
        length = struct.pack('>I', 1 + len(payload))
        self.writer.write(length + bytes([message_id]) + payload)
        await self.writer.drain()

    async def read_message(self):
        """Read and parse a single message, keepalives return None"""
        length_bytes = await self.reader.readexactly(4)
        length = struct.unpack('>I', length_bytes)[0]

        if length == 0:
            return None  # keep-alive

        message_id = (await self.reader.readexactly(1))[0]
        payload = await self.reader.readexactly(length - 1) if length > 1 else b''

        self._handle_message(message_id, payload)
        return message_id, payload

    def _handle_message(self, message_id, payload):
        if message_id == CHOKE:
            self.peer_choked = True
        elif message_id == UNCHOKE:
            self.peer_choked = False
        elif message_id == INTERESTED:
            self.peer_interested = True
        elif message_id == NOT_INTERESTED:
            self.peer_interested = False
        elif message_id == BITFIELD:
            self.bitfield = bytearray(payload)
        elif message_id == HAVE:
            index = struct.unpack('>I', payload)[0]
            if self.bitfield is not None:
                byte_index, bit_index = divmod(index, 8)
                self.bitfield[byte_index] |= 1 << (7 - bit_index)

    def has_piece(self, index):
        if self.bitfield is None:
            return False
        byte_index, bit_index = divmod(index, 8)
        if byte_index >= len(self.bitfield):
            return False
        return bool(self.bitfield[byte_index] & (1 << (7 - bit_index)))

    async def close(self):
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()
