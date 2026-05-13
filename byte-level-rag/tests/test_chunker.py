import pytest
from src.chunker import SmartChunker, Chunk

# Helper to convert string to byte list for tests
def to_byte_list(text: str) -> list[int]:
    return list(text.encode('utf-8'))

def test_init_valid():
    """Tests that the chunker can be initialized with valid parameters."""
    chunker = SmartChunker(chunk_size=100, overlap=20)
    assert chunker.chunk_size == 100
    assert chunker.overlap == 20

def test_init_invalid():
    """Tests that the chunker raises errors for invalid initialization parameters."""
    with pytest.raises(ValueError):
        SmartChunker(chunk_size=0)
    with pytest.raises(ValueError):
        SmartChunker(overlap=-1)
    with pytest.raises(ValueError):
        SmartChunker(chunk_size=50, overlap=50)

def test_chunk_empty_input():
    """Tests that chunking an empty list results in an empty list of chunks."""
    chunker = SmartChunker()
    assert chunker.chunk_bytes([]) == []

def test_chunk_shorter_than_chunk_size():
    """Tests chunking a byte list that is shorter than the chunk size."""
    chunker = SmartChunker(chunk_size=100)
    byte_list = to_byte_list("This is a short text.")
    chunks = chunker.chunk_bytes(byte_list)
    assert len(chunks) == 1
    assert chunks[0].byte_sequence == byte_list
    assert chunks[0].metadata['total_chunks'] == 1

def test_chunking_simple_ascii():
    """Tests basic chunking with a simple ASCII string."""
    chunker = SmartChunker(chunk_size=10, overlap=3)
    byte_list = to_byte_list("abcdefghijklmnopqrstuvwxyz")
    chunks = chunker.chunk_bytes(byte_list)

    assert len(chunks) == 4
    assert chunks[0].byte_sequence == to_byte_list("abcdefghij")
    assert chunks[1].byte_sequence == to_byte_list("hijklmnopq")
    assert chunks[2].byte_sequence == to_byte_list("opqrstuvwx")
    assert chunks[3].byte_sequence == to_byte_list("vwxyz")

def test_dechunking_reconstruction():
    """Tests that the original byte sequence can be perfectly reconstructed."""
    chunker = SmartChunker(chunk_size=15, overlap=5)
    original_text = "This is a longer sentence to test the reconstruction of the chunking process."
    byte_list = to_byte_list(original_text)
    chunks = chunker.chunk_bytes(byte_list)
    reconstructed_bytes = chunker.dechunk(chunks)

    assert reconstructed_bytes == byte_list
    assert bytes(reconstructed_bytes).decode('utf-8') == original_text

def test_utf8_boundary_respect():
    """Ensures that chunks do not split in the middle of a multi-byte character."""
    # The '€' sign is 3 bytes: [226, 130, 172]
    # We set the chunk size so the boundary falls inside it.
    text = "123456789€12345"
    byte_list = to_byte_list(text)

    # Boundary at 10 would be in the middle of '€'
    chunker = SmartChunker(chunk_size=10, overlap=2)
    chunks = chunker.chunk_bytes(byte_list)

    assert len(chunks) == 2
    # The first chunk should end right before '€', at index 9
    assert chunks[0].byte_sequence == to_byte_list("123456789")
    assert chunks[0].metadata['byte_end'] == 9

    # The second chunk should start from the overlap point and contain the '€'
    assert chunks[1].byte_sequence == to_byte_list("89€12345")

def test_metadata_generation():
    """Verifies that the metadata for each chunk is generated correctly."""
    chunker = SmartChunker(chunk_size=20, overlap=5)
    byte_list = to_byte_list("This is a test sentence for checking metadata accuracy.")
    chunks = chunker.chunk_bytes(byte_list)

    assert len(chunks) == 4

    # Check first chunk (0-20)
    assert chunks[0].metadata['chunk_id'] == 0
    assert chunks[0].metadata['total_chunks'] == 4
    assert chunks[0].metadata['byte_start'] == 0
    assert chunks[0].metadata['byte_end'] == 20
    assert chunks[0].metadata['overlap_prev'] == 0
    assert chunks[0].metadata['overlap_next'] == 5

    # Check second chunk (15-35)
    assert chunks[1].metadata['chunk_id'] == 1
    assert chunks[1].metadata['byte_start'] == 15
    assert chunks[1].metadata['byte_end'] == 35
    assert chunks[1].metadata['overlap_prev'] == 5
    assert chunks[1].metadata['overlap_next'] == 5

    # Check third chunk (30-50)
    assert chunks[2].metadata['chunk_id'] == 2
    assert chunks[2].metadata['byte_start'] == 30
    assert chunks[2].metadata['byte_end'] == 50
    assert chunks[2].metadata['overlap_prev'] == 5
    assert chunks[2].metadata['overlap_next'] == 5

    # Check fourth chunk (45-55)
    assert chunks[3].metadata['chunk_id'] == 3
    assert chunks[3].metadata['byte_start'] == 45
    assert chunks[3].metadata['byte_end'] == len(byte_list) # 55
    assert chunks[3].metadata['overlap_prev'] == 5
    assert chunks[3].metadata['overlap_next'] == 0
