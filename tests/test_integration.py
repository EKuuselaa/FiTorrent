import asyncio
import hashlib
import struct

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from src.bencode import encode
from src.download_manager import DownloadManager
from src.peer import PROTOCOL, INTERESTED, UNCHOKE, REQUEST, PIECE, BITFIELD
from src.torrent_parser import TorrentFile

CONTENT = b'A' * 16 + b'B' * 16 + b'C' * 5  # 3 pieces: two full, one short
PIECE_LENGTH = 16
FILE_NAME = 'testfile.bin'


def piece_at(index):
    return CONTENT[index * PIECE_LENGTH:(index + 1) * PIECE_LENGTH]


def build_torrent_file(tmp_path, announce_url):
    hashes = b''.join(hashlib.sha1(piece_at(i)).digest() for i in range(3))
    info = {
        b'piece length': PIECE_LENGTH,
        b'pieces': hashes,
        b'name': FILE_NAME.encode(),
        b'length': len(CONTENT),
    }
    torrent_dict = {b'announce': announce_url.encode(), b'info': info}

    path = tmp_path / 'test.torrent'
    path.write_bytes(encode(torrent_dict))
    return str(path)


async def _handle_seeder_connection(reader, writer, info_hash, own_peer_id):
    try:
        handshake = await reader.readexactly(49 + len(PROTOCOL))
        assert handshake[1 + len(PROTOCOL) + 8:1 + len(PROTOCOL) + 8 + 20] == info_hash

        response = bytes([len(PROTOCOL)]) + PROTOCOL + bytes(8) + info_hash + own_peer_id
        writer.write(response)

        bitfield_payload = b'\xff'
        writer.write(struct.pack('>IB', 1 + len(bitfield_payload), BITFIELD) + bitfield_payload)
        await writer.drain()

        while True:
            length_bytes = await reader.readexactly(4)
            length = struct.unpack('>I', length_bytes)[0]
            if length == 0:
                continue
            message_id = (await reader.readexactly(1))[0]
            payload = await reader.readexactly(length - 1) if length > 1 else b''

            if message_id == INTERESTED:
                writer.write(struct.pack('>IB', 1, UNCHOKE))
                await writer.drain()
            elif message_id == REQUEST:
                index, begin, req_length = struct.unpack('>III', payload)
                block = piece_at(index)[begin:begin + req_length]
                piece_payload = struct.pack('>II', index, begin) + block
                writer.write(struct.pack('>IB', 1 + len(piece_payload), PIECE) + piece_payload)
                await writer.drain()
    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass
    finally:
        writer.close()


@pytest.fixture
async def seeder():
    """A minimal local peer that seeds CONTENT for any torrent with a matching info_hash"""
    connections = {}

    async def handle(reader, writer):
        info_hash = connections['info_hash']
        peer_id = connections['peer_id']
        await _handle_seeder_connection(reader, writer, info_hash, peer_id)

    server = await asyncio.start_server(handle, '127.0.0.1', 0)
    port = server.sockets[0].getsockname()[1]

    def configure(info_hash, peer_id):
        connections['info_hash'] = info_hash
        connections['peer_id'] = peer_id
        return port

    yield configure

    server.close()
    await server.wait_closed()


@pytest.fixture
async def tracker(seeder):
    """A local HTTP tracker that always points at the seeder fixture"""
    state = {}

    async def handle_announce(request):
        body = encode({b'interval': 1800, b'peers': state['peers']})
        return web.Response(body=body)

    app = web.Application()
    app.router.add_get('/announce', handle_announce)
    server = TestServer(app)
    await server.start_server()

    def configure(info_hash, peer_id):
        port = seeder(info_hash, peer_id)
        state['peers'] = bytes([127, 0, 0, 1]) + struct.pack('>H', port)

    yield server, configure

    await server.close()


async def test_download_manager_downloads_and_reassembles_file(tmp_path, tracker):
    server, configure_tracker = tracker
    announce_url = str(server.make_url('/announce'))
    torrent_path = build_torrent_file(tmp_path, announce_url)
    torrent = TorrentFile(torrent_path)

    peer_id = b'-FT0001-000000000001'
    configure_tracker(torrent.info_hash, b'-SEED01-000000000000')

    output_dir = tmp_path / 'downloads'
    manager = DownloadManager(torrent, str(output_dir), peer_id, max_peers=1)

    await asyncio.wait_for(manager.start(), timeout=10)

    assert manager.piece_manager.is_complete()
    assert (output_dir / FILE_NAME).read_bytes() == CONTENT
