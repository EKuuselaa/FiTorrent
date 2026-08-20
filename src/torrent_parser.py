# src/torrent_parser.py
import hashlib
from src.bencode import decode, encode

class TorrentFile:
    def __init__(self, filepath):
        with open(filepath, 'rb') as f:
            self.data = decode(f.read())
        
        self.announce = self.data[b'announce'].decode()
        self.info = self.data[b'info']
        self.piece_length = self.info[b'piece length']
        self.pieces = self.info[b'pieces']
        self.name = self.info[b'name'].decode()
        
        # Total size
        if b'files' in self.info:  # Multiple files
            self.files = self.info[b'files']
            self.total_length = sum(f[b'length'] for f in self.files)
        else:  # Single file
            self.total_length = self.info[b'length']
        
        self.num_pieces = len(self.pieces) // 20
        self.info_hash = hashlib.sha1(encode(self.info)).digest()
    
    def get_piece_hash(self, index):
        """Get SHA1 hash for piece at index"""
        return self.pieces[index * 20:(index + 1) * 20]