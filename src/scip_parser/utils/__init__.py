"""Utility functions for SCIP parsing."""

from src.scip_parser.utils.documentation import (
    extract_clean_documentation,
    merge_documentation,
    remove_code_blocks,
    clean_whitespace,
)

from src.scip_parser.utils.signature import (
    extract_signature,
    extract_signature_from_signature_documentation,
    extract_signature_from_markdown,
    extract_signature_from_any,
)

__all__ = [
    # Documentation utilities
    "extract_clean_documentation",
    "merge_documentation",
    "remove_code_blocks",
    "clean_whitespace",
    # Signature utilities
    "extract_signature",
    "extract_signature_from_signature_documentation",
    "extract_signature_from_markdown",
    "extract_signature_from_any",
]
