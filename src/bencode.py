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