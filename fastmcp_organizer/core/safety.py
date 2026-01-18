import os
from pathlib import Path
from fastmcp_organizer.core.interfaces import ISafetyPolicy

class StrictSafetyPolicy(ISafetyPolicy):
    def __init__(self, allow_symlinks: bool = False):
        self.allow_symlinks = allow_symlinks

    def validate_path(self, root: Path, target: Path) -> bool:
        """
        Ensures target is within root and handles symlinks.
        """
        try:
            # Resolve symlinks and relative paths
            real_root = root.resolve(strict=True)
            # Target might not exist yet (if it's a destination), so we resolve parent
            if target.exists():
                real_target = target.resolve(strict=True)
            else:
                real_target = target.resolve(strict=False) 
                
            # Check for symlinks if not allowed
            if not self.allow_symlinks and target.exists() and os.path.islink(target):
                return False
                
        except FileNotFoundError:
            return False

        # Check if target is actually inside root
        return real_target.is_relative_to(real_root)

    def validate_move(self, src: Path, dest: Path) -> None:
        if os.path.islink(src):
            if not self.allow_symlinks:
                raise ValueError(f"Symlink movement blocked: {src}")
        
        # Additional checks can go here
