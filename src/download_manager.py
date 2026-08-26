import asyncio
import os
import struct

from src.peer import PeerConnection, PIECE, UNCHOKE, BLOCK_SIZE
from src.piece_manager import PieceManager
from src.tracker import TrackerClient


class DownloadManager:
    def __init__(self, torrent, output_dir, peer_id, max_peers=10):
        self.torrent = torrent
        self.output_path = os.path.join(output_dir, torrent.name)
        self.peer_id = peer_id
        self.max_peers = max_peers

        self.tracker = TrackerClient(torrent, peer_id)
        self.piece_manager = PieceManager(torrent)

    async def start(self):
        """Announce to the tracker, download all pieces, then assemble the file"""
        peers = await self.tracker.announce(left=self.torrent.total_length)

        workers = [
            asyncio.create_task(self._worker(ip, port))
            for ip, port in peers[:self.max_peers]
        ]
        await self.piece_manager.join()

        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

        self.piece_manager.assemble_file(self.output_path)

    async def _worker(self, ip, port):
        """Connect to a single peer and download pieces from it until the queue is empty"""
        conn = PeerConnection(ip, port, self.torrent.info_hash, self.peer_id)
        try:
            await conn.connect()
            await conn.send_interested()
            await self._wait_for_unchoke(conn)

            while True:
                index = await self.piece_manager.get_index()
                try:
                    if conn.bitfield is not None and not conn.has_piece(index):
                        await self.piece_manager.requeue(index)
                        await asyncio.sleep(0.1)
                        continue

                    data = await self._download_piece(conn, index)
                    if data is None or not await self.piece_manager.store(index, data):
                        await self.piece_manager.requeue(index)
                finally:
                    self.piece_manager.task_done()
        except (ConnectionError, OSError, asyncio.IncompleteReadError):
            return
        finally:
            await conn.close()

    async def _wait_for_unchoke(self, conn, timeout=10):
        async def _wait():
            while conn.peer_choked:
                message = await conn.read_message()
                if message and message[0] == UNCHOKE:
                    break
        await asyncio.wait_for(_wait(), timeout)

    async def _download_piece(self, conn, index):
        """Request and assemble every block of a single piece"""
        piece_length = self.piece_manager.piece_length(index)
        blocks = bytearray(piece_length)
        offset = 0

        while offset < piece_length:
            length = min(BLOCK_SIZE, piece_length - offset)
            await conn.send_request(index, offset, length)

            message_id, payload = await conn.read_message()
            while message_id != PIECE:
                message_id, payload = await conn.read_message()

            begin = struct.unpack('>I', payload[4:8])[0]
            block = payload[8:]
            blocks[begin:begin + len(block)] = block
            offset += length

        return bytes(blocks)

    @property
    def progress(self):
        return self.piece_manager.progress
