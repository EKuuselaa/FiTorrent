# src/bencode.py
def decode(data: bytes):
    """Decode bencode data"""
    def _decode(data, index=0):
        if data[index:index+1] == b'i':  # Integer
            end = data.index(b'e', index)
            return int(data[index+1:end]), end + 1
        elif data[index:index+1] == b'l':  # List
            result = []
            index += 1
            while data[index:index+1] != b'e':
                value, index = _decode(data, index)
                result.append(value)
            return result, index + 1
        elif data[index:index+1] == b'd':  # Dictionary
            result = {}
            index += 1
            while data[index:index+1] != b'e':
                key, index = _decode(data, index)
                value, index = _decode(data, index)
                result[key] = value
            return result, index + 1
        elif data[index:index+1].isdigit():  # String
            colon = data.index(b':', index)
            length = int(data[index:colon])
            start = colon + 1
            return data[start:start+length], start + length
    
    result, _ = _decode(data)
    return result


def encode(data) -> bytes:
    """Encode data to bencode format"""
    if isinstance(data, int):
        return b'i' + str(data).encode() + b'e'

    elif isinstance(data, bytes):
        return str(len(data)).encode() + b':' + data

    elif isinstance(data, str):
        encoded_str = data.encode()
        return str(len(encoded_str)).encode() + b':' + encoded_str

    elif isinstance(data, list):
        return b'l' + b''.join(encode(item) for item in data) + b'e'

    elif isinstance(data, dict):
        # Bencode spec requires dict keys to be sorted (as raw bytes)
        result = b'd'
        for key in sorted(data.keys()):
            result += encode(key)
            result += encode(data[key])
        result += b'e'
        return result

    else:
        raise TypeError(f"Type {type(data)} not bencodable")