import hashlib
from pathlib import Path
from fastmcp_organizer.core.interfaces import IScanner, FileMetadata
from fastmcp_organizer.core.reader import FileReader

class CompositeScanner(IScanner):
    def scan_file(self, path: Path) -> FileMetadata:
        stats = path.stat()
        
        # 1. Cheap Metadata Hash
        hasher = hashlib.sha256()
        hasher.update(str(stats.st_size).encode())
        hasher.update(str(stats.st_mtime).encode())
        
        # 2. Semantic Sampling (Content Hash)
        sample = FileReader.read_sample(path)
        hasher.update(sample)
        
        composite_hash = hasher.hexdigest()
        
        return FileMetadata(
            path=str(path),
            size_bytes=stats.st_size,
            mtime=stats.st_mtime,
            hash=composite_hash,
            content_sample=sample
        )
