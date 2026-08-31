# FiTorrent

A minimal BitTorrent client written in Python with `asyncio`. It parses `.torrent`
files, announces to an HTTP tracker, downloads pieces from multiple peers in
parallel, verifies each piece's SHA1 hash, and reassembles the final file.

## Features

- Bencode encoder/decoder ([src/bencode.py](src/bencode.py))
- `.torrent` file parsing ([src/torrent_parser.py](src/torrent_parser.py))
- HTTP tracker announce with compact peer parsing ([src/tracker.py](src/tracker.py))
- Peer wire protocol (handshake, choke/interest, bitfield/have, block requests) ([src/peer.py](src/peer.py))
- Piece tracking and SHA1 verification ([src/piece_manager.py](src/piece_manager.py))
- Concurrent multi-peer downloading and file assembly ([src/download_manager.py](src/download_manager.py))

Currently supports single-file torrents over HTTP trackers. No DHT, magnet
links, or seeding/uploading yet.

## Requirements

- Python 3.11+

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py path/to/file.torrent -o output_dir
```

- `torrent` — path to the `.torrent` file (required)
- `-o, --output` — directory to save the downloaded file into (default: current directory)

Progress is printed to the terminal while the download runs.

## Development

Install dev dependencies (includes test tooling):

```bash
pip install -r requirements-dev.txt
```

Run the test suite:

```bash
python -m pytest
```

Tests cover bencode round-trips, piece hash verification, peer wire-protocol
framing, tracker announce parsing, and a full end-to-end integration test that
runs a local fake tracker and seeding peer to exercise the whole download path.

Tests run automatically on push/PR via [GitHub Actions](.github/workflows/tests.yml).

## Project structure

```
main.py                  CLI entry point
src/
  bencode.py              Bencode encode/decode
  torrent_parser.py       .torrent file parsing
  tracker.py              HTTP tracker client
  peer.py                 Peer connection / wire protocol
  piece_manager.py        Piece queue, hash verification, file assembly
  download_manager.py     Coordinates tracker + peers + pieces
tests/                    pytest test suite
```
