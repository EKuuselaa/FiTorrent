import struct

from aiohttp import web
from aiohttp.test_utils import TestServer

from src.bencode import encode
from src.tracker import TrackerClient


class FakeTorrent:
    def __init__(self, announce_url):
        self.announce = announce_url
        self.info_hash = b'\x01' * 20


def test_parse_peers_decodes_compact_format():
    client = TrackerClient(torrent=None, peer_id=b'peer')
    peers_data = bytes([127, 0, 0, 1]) + struct.pack('>H', 6881) + bytes([10, 0, 0, 5]) + struct.pack('>H', 51413)

    peers = client._parse_peers(peers_data)

    assert peers == [('127.0.0.1', 6881), ('10.0.0.5', 51413)]


async def test_announce_parses_response_from_tracker():
    peers_data = bytes([127, 0, 0, 1]) + struct.pack('>H', 6881)
    seen_params = {}

    async def handle_announce(request):
        seen_params.update(request.query)
        body = encode({b'interval': 1800, b'peers': peers_data})
        return web.Response(body=body)

    app = web.Application()
    app.router.add_get('/announce', handle_announce)
    server = TestServer(app)
    await server.start_server()
    try:
        torrent = FakeTorrent(announce_url=str(server.make_url('/announce')))
        client = TrackerClient(torrent, peer_id=b'-FT0001-000000000000')

        peers = await client.announce(left=100)

        assert peers == [('127.0.0.1', 6881)]
        assert seen_params['left'] == '100'
        assert seen_params['event'] == 'started'
    finally:
        await server.close()
