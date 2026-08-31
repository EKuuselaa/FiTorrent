import asyncio
import struct

import pytest

from src.peer import (
    PeerConnection, PROTOCOL,
    CHOKE, UNCHOKE, INTERESTED, BITFIELD, HAVE, PIECE,
)


class FakeWriter:
    def __init__(self):
        self.buffer = bytearray()
        self.closed = False

    def write(self, data):
        self.buffer.extend(data)

    async def drain(self):
        pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


def make_conn():
    conn = PeerConnection('127.0.0.1', 6881, info_hash=b'\x01' * 20, peer_id=b'\x02' * 20)
    conn.reader = asyncio.StreamReader()
    conn.writer = FakeWriter()
    return conn


def encode_message(message_id, payload=b''):
    length = struct.pack('>I', 1 + len(payload))
    return length + bytes([message_id]) + payload


async def test_send_interested_sets_flag_and_writes_message():
    conn = make_conn()
    await conn.send_interested()

    assert conn.interested is True
    assert conn.writer.buffer == struct.pack('>IB', 1, INTERESTED)


async def test_send_request_encodes_index_begin_length():
    conn = make_conn()
    await conn.send_request(index=3, begin=16384, length=16384)

    expected = struct.pack('>IB', 13, 6) + struct.pack('>III', 3, 16384, 16384)
    assert conn.writer.buffer == expected


async def test_read_message_keepalive_returns_none():
    conn = make_conn()
    conn.reader.feed_data(struct.pack('>I', 0))

    assert await conn.read_message() is None


async def test_read_message_parses_piece_payload():
    conn = make_conn()
    payload = struct.pack('>II', 2, 0) + b'blockdata'
    conn.reader.feed_data(encode_message(PIECE, payload))

    message_id, received_payload = await conn.read_message()

    assert message_id == PIECE
    assert received_payload == payload


@pytest.mark.parametrize('message_id, flag_name, expected', [
    (CHOKE, 'peer_choked', True),
    (UNCHOKE, 'peer_choked', False),
    (INTERESTED, 'peer_interested', True),
])
async def test_read_message_updates_connection_state(message_id, flag_name, expected):
    conn = make_conn()
    conn.reader.feed_data(encode_message(message_id))

    await conn.read_message()

    assert getattr(conn, flag_name) == expected


async def test_bitfield_message_sets_bitfield():
    conn = make_conn()
    conn.reader.feed_data(encode_message(BITFIELD, b'\xff\x00'))

    await conn.read_message()

    assert conn.bitfield == bytearray(b'\xff\x00')


async def test_have_message_sets_bit_in_existing_bitfield():
    conn = make_conn()
    conn.bitfield = bytearray(b'\x00\x00')
    conn.reader.feed_data(encode_message(HAVE, struct.pack('>I', 9)))

    await conn.read_message()

    assert conn.has_piece(9) is True


async def test_has_piece_false_without_bitfield():
    conn = make_conn()
    assert conn.has_piece(0) is False


async def test_has_piece_false_when_index_out_of_range():
    conn = make_conn()
    conn.bitfield = bytearray(b'\x00')
    assert conn.has_piece(100) is False


async def test_handshake_succeeds_with_matching_info_hash():
    conn = make_conn()
    response = (
        bytes([len(PROTOCOL)]) + PROTOCOL + bytes(8) + conn.info_hash + b'\x03' * 20
    )
    conn.reader.feed_data(response)

    result = await conn._handshake()

    assert result == response


async def test_handshake_raises_on_info_hash_mismatch():
    conn = make_conn()
    other_hash = b'\x99' * 20
    response = (
        bytes([len(PROTOCOL)]) + PROTOCOL + bytes(8) + other_hash + b'\x03' * 20
    )
    conn.reader.feed_data(response)

    with pytest.raises(ConnectionError):
        await conn._handshake()
