import hashlib

import pytest

from src.piece_manager import PieceManager


class FakeTorrent:
    """3 pieces of 4 bytes, last piece is a short 2-byte remainder"""

    def __init__(self, piece_data):
        self.piece_data = piece_data
        self.num_pieces = len(piece_data)
        self.piece_length = 4
        self.total_length = sum(len(p) for p in piece_data)

    def get_piece_hash(self, index):
        return hashlib.sha1(self.piece_data[index]).digest()


@pytest.fixture
def piece_data():
    return [b'aaaa', b'bbbb', b'cc']


@pytest.fixture
def manager(piece_data):
    return PieceManager(FakeTorrent(piece_data))


def test_queue_seeded_with_every_index(manager):
    assert manager.queue.qsize() == 3


def test_piece_length_uses_remainder_for_last_piece(manager):
    assert manager.piece_length(0) == 4
    assert manager.piece_length(1) == 4
    assert manager.piece_length(2) == 2


def test_verify_accepts_matching_data(manager, piece_data):
    assert manager.verify(0, piece_data[0]) is True


def test_verify_rejects_corrupt_data(manager):
    assert manager.verify(0, b'wrong') is False


async def test_store_accepts_and_records_valid_piece(manager, piece_data):
    accepted = await manager.store(0, piece_data[0])

    assert accepted is True
    assert manager.pieces[0] == piece_data[0]
    assert manager.completed == 1
    assert manager.downloaded == 4


async def test_store_rejects_corrupt_piece_without_recording(manager):
    accepted = await manager.store(0, b'corrupt')

    assert accepted is False
    assert manager.pieces[0] is None
    assert manager.completed == 0


async def test_is_complete_only_after_every_piece_stored(manager, piece_data):
    for index, data in enumerate(piece_data):
        assert manager.is_complete() is False
        await manager.store(index, data)

    assert manager.is_complete() is True


async def test_progress_tracks_completed_fraction(manager, piece_data):
    assert manager.progress == 0
    await manager.store(0, piece_data[0])
    assert manager.progress == pytest.approx(1 / 3)


async def test_assemble_file_writes_pieces_in_order(tmp_path, manager, piece_data):
    for index, data in enumerate(piece_data):
        await manager.store(index, data)

    output_path = tmp_path / 'out' / 'result.bin'
    manager.assemble_file(str(output_path))

    assert output_path.read_bytes() == b''.join(piece_data)


def test_assemble_file_fills_missing_pieces_with_nothing(tmp_path, manager, piece_data):
    output_path = tmp_path / 'result.bin'
    manager.assemble_file(str(output_path))

    assert output_path.read_bytes() == b''


async def test_requeue_puts_index_back_on_queue(manager):
    index = await manager.get_index()
    manager.task_done()
    await manager.requeue(index)

    assert manager.queue.qsize() == 3
