import asyncio
import hashlib
import os
import struct

from src.peer import PeerConnection, PIECE, UNCHOKE, BLOCK_SIZE
from src.tracker import TrackerClient


class DownloadManager:
    def __init__(self, torrent, output_dir, peer_id, max_peers=10):
        self.torrent = torrent
        self.output_path = os.path.join(output_dir, torrent.name)
        self.peer_id = peer_id
        self.max_peers = max_peers

        self.tracker = TrackerClient(torrent, peer_id)

        self.piece_queue = asyncio.Queue()
        for index in range(torrent.num_pieces):
            self.piece_queue.put_nowait(index)

        self.pieces = [None] * torrent.num_pieces
        self.completed = 0
        self.downloaded = 0
        self.lock = asyncio.Lock()

    async def start(self):
        """Announce to the tracker, download all pieces, then assemble the file"""
        peers = await self.tracker.announce(left=self.torrent.total_length)

        workers = [
            asyncio.create_task(self._worker(ip, port))
            for ip, port in peers[:self.max_peers]
        ]
        await self.piece_queue.join()

        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

        self._assemble_file()

    async def _worker(self, ip, port):
        """Connect to a single peer and download pieces from it until the queue is empty"""
        conn = PeerConnection(ip, port, self.torrent.info_hash, self.peer_id)
        try:
            await conn.connect()
            await conn.send_interested()
            await self._wait_for_unchoke(conn)

            while True:
                index = await self.piece_queue.get()
                try:
                    if conn.bitfield is not None and not conn.has_piece(index):
                        await self.piece_queue.put(index)
                        await asyncio.sleep(0.1)
                        continue

                    data = await self._download_piece(conn, index)
                    if data is not None:
                        await self._store_piece(index, data)
                    else:
                        await self.piece_queue.put(index)
                finally:
                    self.piece_queue.task_done()
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
        """Request and assemble every block of a single piece, verifying its hash"""
        piece_length = self._piece_length(index)
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

        if hashlib.sha1(bytes(blocks)).digest() != self.torrent.get_piece_hash(index):
            return None
        return bytes(blocks)

    def _piece_length(self, index):
        if index == self.torrent.num_pieces - 1:
            return self.torrent.total_length - self.torrent.piece_length * index
        return self.torrent.piece_length

    async def _store_piece(self, index, data):
        async with self.lock:
            self.pieces[index] = data
            self.completed += 1
            self.downloaded += len(data)

    def _assemble_file(self):
        os.makedirs(os.path.dirname(self.output_path) or '.', exist_ok=True)
        with open(self.output_path, 'wb') as f:
            for piece in self.pieces:
                f.write(piece or b'')

    @property
    def progress(self):
        return self.completed / self.torrent.num_pieces
