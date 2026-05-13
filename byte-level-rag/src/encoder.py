from typing import List

class ByteEncoder:
    """
    A robust encoder for converting text to and from UTF-8 byte sequences.
    """

    def encode(self, text: str) -> bytes:
        """
        Encodes a string into a sequence of bytes using UTF-8.

        Args:
            text: The string to encode.

        Returns:
            The UTF-8 encoded bytes.
        """
        return text.encode('utf-8')

    def decode(self, data: bytes) -> str:
        """
        Decodes a sequence of bytes into a string using UTF-8,
        replacing any characters that cause decoding errors.

        Args:
            data: The bytes to decode.

        Returns:
            The decoded string.
        """
        return data.decode('utf-8', errors='replace')

    def to_vector_compatible(self, data: bytes) -> List[int]:
        """
        Converts a byte sequence into a list of integers (0-255).

        Args:
            data: The byte sequence.

        Returns:
            A list of integers representing the bytes.
        """
        return list(data)

    def validate_sequence(self, byte_list: List[int]) -> bool:
        """
        Validates if a list of integers represents a valid UTF-8 sequence.

        Args:
            byte_list: A list of integers (0-255).

        Returns:
            True if the sequence is valid UTF-8, False otherwise.
        """
        try:
            bytes(byte_list).decode('utf-8')
            return True
        except UnicodeDecodeError:
            return False
