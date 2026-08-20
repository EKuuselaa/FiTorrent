# src/tracker.py
import aiohttp
import asyncio
from urllib.parse import urlencode
import struct

class TrackerClient:
    def __init__(self, torrent, peer_id):
        self.torrent = torrent
        self.peer_id = peer_id
    
    async def announce(self, downloaded=0, uploaded=0, left=0):
        """Announce to tracker"""
        params = {
            'info_hash': self.torrent.info_hash,
            'peer_id': self.peer_id,
            'port': 6881,
            'uploaded': uploaded,
            'downloaded': downloaded,
            'left': left,
            'compact': 1,
            'event': 'started'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.torrent.announce, params=params) as resp:
                response = decode(await resp.read())
                return self._parse_peers(response[b'peers'])
    
    def _parse_peers(self, peers_data):
        """Parse compact peer format"""
        peers = []
        for i in range(0, len(peers_data), 6):
            ip = '.'.join(str(b) for b in peers_data[i:i+4])
            port = struct.unpack('>H', peers_data[i+4:i+6])[0]
            peers.append((ip, port))
        return peers