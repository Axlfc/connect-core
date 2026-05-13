from typing import List
import numpy as np

class ByteNormalizer:
    """
    Handles normalization of byte sequences and embeddings.
    """

    def normalize_bytes(self, byte_list: List[int]) -> np.ndarray:
        """
        Scales a list of byte values [0-255] to a float array [0.0-1.0].

        Args:
            byte_list: A list of integers representing bytes.

        Returns:
            A NumPy array of floats, scaled to the range [0.0, 1.0].
        """
        return np.array(byte_list) / 255.0

    def pad_or_truncate(self, arr: np.ndarray, target_len: int) -> np.ndarray:
        """
        Pads or truncates a NumPy array to a target length.

        Args:
            arr: The input NumPy array.
            target_len: The desired length of the array.

        Returns:
            The modified array with the target length.
        """
        current_len = len(arr)
        if current_len > target_len:
            return arr[:target_len]
        elif current_len < target_len:
            padding = np.zeros(target_len - current_len)
            return np.concatenate([arr, padding])
        return arr

    def normalize_embedding(self, embedding: np.ndarray) -> np.ndarray:
        """
        Applies L2 normalization to a vector (embedding).

        Args:
            embedding: The NumPy array representing the embedding.

        Returns:
            The L2-normalized embedding. Returns a zero vector if the norm is zero.
        """
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm
