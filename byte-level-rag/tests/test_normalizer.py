import pytest
import numpy as np
from src.normalizer import ByteNormalizer

@pytest.fixture
def normalizer():
    """Provides a ByteNormalizer instance for testing."""
    return ByteNormalizer()

def test_normalize_bytes(normalizer):
    """Tests the scaling of byte values to the [0, 1] range."""
    byte_list = [0, 127.5, 255]
    expected_array = np.array([0.0, 0.5, 1.0])
    result = normalizer.normalize_bytes(byte_list)
    assert isinstance(result, np.ndarray)
    np.testing.assert_allclose(result, expected_array)

def test_normalize_bytes_empty(normalizer):
    """Tests normalizing an empty list."""
    assert len(normalizer.normalize_bytes([])) == 0

def test_pad_or_truncate_truncation(normalizer):
    """Tests truncating an array that is too long."""
    arr = np.array([1, 2, 3, 4, 5])
    target_len = 3
    expected = np.array([1, 2, 3])
    result = normalizer.pad_or_truncate(arr, target_len)
    np.testing.assert_array_equal(result, expected)
    assert len(result) == target_len

def test_pad_or_truncate_padding(normalizer):
    """Tests padding an array that is too short."""
    arr = np.array([1, 2, 3])
    target_len = 5
    expected = np.array([1, 2, 3, 0, 0])
    result = normalizer.pad_or_truncate(arr, target_len)
    np.testing.assert_array_equal(result, expected)
    assert len(result) == target_len

def test_pad_or_truncate_no_change(normalizer):
    """Tests an array that already has the target length."""
    arr = np.array([1, 2, 3, 4, 5])
    target_len = 5
    expected = np.array([1, 2, 3, 4, 5])
    result = normalizer.pad_or_truncate(arr, target_len)
    np.testing.assert_array_equal(result, expected)
    assert len(result) == target_len

def test_normalize_embedding(normalizer):
    """Tests L2 normalization of a standard vector."""
    embedding = np.array([1.0, 2.0, 3.0, 4.0])
    normalized = normalizer.normalize_embedding(embedding)
    norm = np.linalg.norm(normalized)
    np.testing.assert_allclose(norm, 1.0)

def test_normalize_embedding_zero_vector(normalizer):
    """Tests L2 normalization of a zero vector, which should remain unchanged."""
    embedding = np.array([0.0, 0.0, 0.0])
    normalized = normalizer.normalize_embedding(embedding)
    np.testing.assert_array_equal(normalized, embedding)

def test_normalize_embedding_already_normalized(normalizer):
    """Tests normalizing a vector that is already L2-normalized."""
    embedding = np.array([1.0, 0.0, 0.0])
    normalized = normalizer.normalize_embedding(embedding)
    np.testing.assert_allclose(normalized, embedding)
    assert np.linalg.norm(normalized) == 1.0
