import hashlib
from config import CHUNK_SIZE


def stream_file(filepath):
    with open(filepath, 'rb') as f:
        while chunk := f.read(CHUNK_SIZE):
            yield chunk


def compute_checksum(filepath):
    sha = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(CHUNK_SIZE):
            sha.update(chunk)
    return sha.hexdigest()
