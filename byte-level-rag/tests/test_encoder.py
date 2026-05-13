import pytest
from src.encoder import ByteEncoder

@pytest.fixture
def encoder():
    """Provides a ByteEncoder instance for testing."""
    return ByteEncoder()

def test_encode_ascii(encoder):
    """Tests encoding of basic ASCII text."""
    text = "Hello, world!"
    expected_bytes = b'Hello, world!'
    assert encoder.encode(text) == expected_bytes

def test_encode_multibyte(encoder):
    """Tests encoding of text with multi-byte UTF-8 characters."""
    text = "Hola, 🌍! ñ"
    expected_bytes = b'Hola, \xf0\x9f\x8c\x8d! \xc3\xb1'
    assert encoder.encode(text) == expected_bytes

def test_decode_valid_utf8(encoder):
    """Tests decoding of a valid UTF-8 byte sequence."""
    data = b'Hola, \xf0\x9f\x8c\x8d! \xc3\xb1'
    expected_text = "Hola, 🌍! ñ"
    assert encoder.decode(data) == expected_text

def test_decode_invalid_utf8(encoder):
    """Tests decoding of an invalid UTF-8 sequence, expecting replacement characters."""
    invalid_data = b'This contains an invalid byte \x80 sequence.'
    expected_text = "This contains an invalid byte � sequence."
    assert encoder.decode(invalid_data) == expected_text

def test_to_vector_compatible(encoder):
    """Tests the conversion of a byte sequence to a list of integers."""
    data = b'ABC'
    expected_list = [65, 66, 67]
    assert encoder.to_vector_compatible(data) == expected_list

def test_validate_sequence_valid_ascii(encoder):
    """Tests validation with a valid ASCII byte sequence."""
    valid_sequence = [72, 101, 108, 108, 111]  # "Hello"
    assert encoder.validate_sequence(valid_sequence) is True

def test_validate_sequence_valid_multibyte(encoder):
    """Tests validation with a valid multi-byte UTF-8 sequence."""
    valid_sequence = [226, 130, 172]  # Euro sign '€'
    assert encoder.validate_sequence(valid_sequence) is True

def test_validate_sequence_invalid_incomplete_multibyte(encoder):
    """Tests validation with an incomplete multi-byte character."""
    invalid_sequence = [226, 130]  # Incomplete Euro sign
    assert encoder.validate_sequence(invalid_sequence) is False

def test_validate_sequence_invalid_start_byte(encoder):
    """Tests validation with an invalid UTF-8 start byte."""
    invalid_sequence = [128, 100, 101] # 0x80 is not a valid start byte
    assert encoder.validate_sequence(invalid_sequence) is False
