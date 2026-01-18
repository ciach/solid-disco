import pytest
import os
from pathlib import Path
from fastmcp_organizer.core.safety import StrictSafetyPolicy
from fastmcp_organizer.core.scanner import CompositeScanner
from fastmcp_organizer.core.classifier import HeuristicClassifier
from fastmcp_organizer.core.interfaces import FileMetadata

def test_safety_policy(tmp_path):
    policy = StrictSafetyPolicy(allow_symlinks=False)
    root = tmp_path / "safe_root"
    root.mkdir()
    
    # Target within root
    target = root / "sub" / "file.txt"
    # Note: validate_path tries to resolve target.parent if target doesn't exist
    # So we should ensure at least the structure is plausible or understandable by resolve
    
    # For validate_path, if target doesn't exist, we resolve(strict=False).
    # However, root MUST exist for resolve(strict=True).
    
    assert policy.validate_path(root, target) is True
    assert policy.validate_path(root, Path("/etc/passwd")) is False

def test_classifier():
    classifier = HeuristicClassifier()
    
    # Test Metadata Classification
    meta_pdf = FileMetadata(path="test.pdf", size_bytes=100, mtime=0, hash="abc")
    res_pdf = classifier.classify(meta_pdf)
    assert res_pdf.requires_deep_scan is True
    
    meta_img = FileMetadata(path="test.png", size_bytes=100, mtime=0, hash="abc")
    res_img = classifier.classify(meta_img)
    assert res_img.category == "Images"
    assert res_img.confidence_score >= 0.9

    # Test Content Classification
    meta_txt = FileMetadata(path="invoice.txt", size_bytes=100, mtime=0, hash="abc")
    res_txt = classifier.classify(meta_txt, content_sample="Total: $500")
    assert res_txt.category == "Financial"

def test_scanner_integrity(tmp_path):
    scanner = CompositeScanner()
    f = tmp_path / "test.txt"
    f.write_text("Hello World" * 1000)
    
    meta1 = scanner.scan_file(f)
    meta2 = scanner.scan_file(f)
    
    assert meta1.hash == meta2.hash
    assert meta1.size_bytes == f.stat().st_size
