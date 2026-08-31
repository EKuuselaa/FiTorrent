from src.bencode import decode, encode


def test_integer_round_trip():
    assert decode(encode(42)) == 42
    assert decode(encode(-7)) == -7


def test_string_round_trip():
    assert decode(encode('hello')) == b'hello'


def test_list_round_trip():
    assert decode(encode([1, b'two', [3, 4]])) == [1, b'two', [3, 4]]


def test_dict_round_trip():
    original = {b'a': 1, b'b': [2, 3], b'c': {b'd': b'e'}}
    assert decode(encode(original)) == original


def test_dict_keys_sorted_in_encoding():
    # Bencode requires sorted dict keys; encoding order should not depend on insertion order
    first = encode({b'z': 1, b'a': 2})
    second = encode({b'a': 2, b'z': 1})
    assert first == second


def test_decode_known_bencoded_values():
    assert decode(b'i42e') == 42
    assert decode(b'5:hello') == b'hello'
    assert decode(b'l4:spam4:eggse') == [b'spam', b'eggs']
    assert decode(b'd3:cow3:moo4:spam4:eggse') == {b'cow': b'moo', b'spam': b'eggs'}
