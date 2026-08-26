import asyncio
import hashlib
import os


class PieceManager:
    """Tracks which pieces still need downloading, verifies completed pieces
    against their SHA1 hash, and assembles the finished pieces into a file"""

    def __init__(self, torrent):
        self.torrent = torrent

        self.queue = asyncio.Queue()
        for index in range(torrent.num_pieces):
            self.queue.put_nowait(index)

        self.pieces = [None] * torrent.num_pieces
        self.completed = 0
        self.downloaded = 0
        self.lock = asyncio.Lock()

    async def get_index(self):
        return await self.queue.get()

    def task_done(self):
        self.queue.task_done()

    async def requeue(self, index):
        await self.queue.put(index)

    async def join(self):
        await self.queue.join()

    def piece_length(self, index):
        if index == self.torrent.num_pieces - 1:
            return self.torrent.total_length - self.torrent.piece_length * index
        return self.torrent.piece_length

    def verify(self, index, data):
        """Check downloaded piece data against the hash recorded in the torrent"""
        return hashlib.sha1(data).digest() == self.torrent.get_piece_hash(index)

    async def store(self, index, data):
        """Verify and record a downloaded piece, returning whether it was accepted"""
        if not self.verify(index, data):
            return False

        async with self.lock:
            self.pieces[index] = data
            self.completed += 1
            self.downloaded += len(data)
        return True

    def is_complete(self):
        return self.completed == self.torrent.num_pieces

    def assemble_file(self, output_path):
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'wb') as f:
            for piece in self.pieces:
                f.write(piece or b'')

    @property
    def progress(self):
        return self.completed / self.torrent.num_pieces
