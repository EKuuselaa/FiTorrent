import argparse
import asyncio
import os
import random
import string
import sys

from src.torrent_parser import TorrentFile
from src.download_manager import DownloadManager


def generate_peer_id():
    """Build a 20-byte peer id using the Azureus-style convention, e.g. -FT0001-xxxxxxxxxxxx"""
    prefix = b'-FT0001-'
    suffix = ''.join(random.choices(string.digits, k=20 - len(prefix)))
    return prefix + suffix.encode()


async def download(torrent_path, output_dir):
    torrent = TorrentFile(torrent_path)
    peer_id = generate_peer_id()
    manager = DownloadManager(torrent, output_dir, peer_id)

    print(f"Downloading '{torrent.name}' ({torrent.num_pieces} pieces)")

    progress_task = asyncio.create_task(_report_progress(manager))
    try:
        await manager.start()
    finally:
        progress_task.cancel()

    print(f"\nDone: saved to {manager.output_path}")


async def _report_progress(manager):
    while True:
        print(f"\rProgress: {manager.progress:.1%}", end='', flush=True)
        await asyncio.sleep(1)


def main():
    parser = argparse.ArgumentParser(description='FiTorrent - a minimal BitTorrent client')
    parser.add_argument('torrent', help='Path to the .torrent file')
    parser.add_argument('-o', '--output', default='.', help='Output directory (default: current directory)')
    args = parser.parse_args()

    if not os.path.isfile(args.torrent):
        print(f"Torrent file not found: {args.torrent}", file=sys.stderr)
        sys.exit(1)

    try:
        asyncio.run(download(args.torrent, args.output))
    except KeyboardInterrupt:
        print("\nInterrupted")


if __name__ == '__main__':
    main()
