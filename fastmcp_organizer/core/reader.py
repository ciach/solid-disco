import os
from pathlib import Path

class FileReader:
    """
    Implements the 'Two-Pass' reading strategy.
    Tier 1 (Fast): Read Head (2KB) + Tail (1KB).
    """
    
    HEAD_SIZE = 4096 # 4KB
    TAIL_SIZE = 4096 # 4KB

    @staticmethod
    def read_sample(path: Path) -> bytes:
        """
        Reads the first 4KB and last 4KB of a file.
        Returns combined bytes.
        """
        try:
            file_size = path.stat().st_size
            if file_size <= (FileReader.HEAD_SIZE + FileReader.TAIL_SIZE):
                return path.read_bytes()
            
            with open(path, 'rb') as f:
                head = f.read(FileReader.HEAD_SIZE)
                f.seek(-FileReader.TAIL_SIZE, os.SEEK_END)
                tail = f.read(FileReader.TAIL_SIZE)
                return head + tail
        except OSError:
            return b""

    @staticmethod
    def read_text_sample(path: Path) -> str:
        """
        Attempts to decode the sample as utf-8, ignoring errors.
        """
        data = FileReader.read_sample(path)
        return data.decode('utf-8', errors='ignore')
