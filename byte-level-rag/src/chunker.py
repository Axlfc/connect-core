from dataclasses import dataclass
from typing import List

@dataclass
class Chunk:
    """
    Represents a chunk of a byte sequence with associated metadata.
    """
    byte_sequence: List[int]
    metadata: dict

class SmartChunker:
    """
    Splits byte sequences into manageable chunks with overlap, respecting UTF-8 character boundaries.
    """
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")
        if overlap < 0:
            raise ValueError("overlap must be non-negative.")
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size.")

        self.chunk_size = chunk_size
        self.overlap = overlap

    def find_safe_boundary(self, byte_list: List[int], position: int) -> int:
        """
        Finds the nearest preceding safe boundary for a UTF-8 sequence.
        A safe boundary is one that is not in the middle of a multi-byte character.
        It moves backwards from the given position until it finds the start of a character.
        """
        if position >= len(byte_list):
            return len(byte_list)

        # Move backwards until we find a byte that is NOT a continuation byte (10xxxxxx)
        while position > 0 and (byte_list[position] & 0xC0) == 0x80:
            position -= 1

        return position

    def chunk_bytes(self, byte_list: List[int]) -> List[Chunk]:
        """
        Splits a list of bytes into chunks, ensuring that no chunk ends in the middle
        of a multi-byte UTF-8 character.
        """
        if not byte_list:
            return []

        chunks = []
        current_pos = 0
        chunk_id = 0

        while current_pos < len(byte_list):
            start = current_pos
            end = min(start + self.chunk_size, len(byte_list))

            safe_end = self.find_safe_boundary(byte_list, end)

            # If boundary search pushes us back to or before the start,
            # it means a single character is very long. We must advance past it.
            if safe_end <= start:
                safe_end = start + 1
                while safe_end < len(byte_list) and (byte_list[safe_end] & 0xC0) == 0x80:
                    safe_end += 1

            chunk_data = byte_list[start:safe_end]
            metadata = {'chunk_id': chunk_id, 'byte_start': start, 'byte_end': safe_end}
            chunks.append(Chunk(byte_sequence=chunk_data, metadata=metadata))

            if safe_end == len(byte_list):
                break

            current_pos = safe_end - self.overlap
            chunk_id += 1

        # Post-process metadata to include chunk relationships
        total_chunks = len(chunks)
        for i, chunk in enumerate(chunks):
            chunk.metadata['total_chunks'] = total_chunks

            prev_chunk_end = chunks[i-1].metadata['byte_end'] if i > 0 else 0
            chunk.metadata['overlap_prev'] = max(0, prev_chunk_end - chunk.metadata['byte_start'])

            next_chunk_start = chunks[i+1].metadata['byte_start'] if i < total_chunks - 1 else len(byte_list)
            chunk.metadata['overlap_next'] = max(0, chunk.metadata['byte_end'] - next_chunk_start)

        return chunks

    def dechunk(self, chunks: List[Chunk]) -> List[int]:
        """
        Reconstructs the original byte sequence from a list of chunks.
        """
        if not chunks:
            return []

        reconstructed = list(chunks[0].byte_sequence)

        for i in range(1, len(chunks)):
            prev_chunk = chunks[i-1]
            current_chunk = chunks[i]

            overlap_count = prev_chunk.metadata['byte_end'] - current_chunk.metadata['byte_start']

            if overlap_count > 0:
                reconstructed.extend(current_chunk.byte_sequence[overlap_count:])
            else:
                # This case implies a gap, which shouldn't happen with this class's chunker
                reconstructed.extend(current_chunk.byte_sequence)

        return reconstructed
