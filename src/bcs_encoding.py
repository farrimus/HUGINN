"""
BCS (Binary Canonical Serialization) encoding for Sui Move types.

BCS is the serialization format used throughout Sui. This module provides utilities
for encoding Move data types to bytes in BCS format, following Sui's specification.

Reference: https://github.com/MystenLabs/bcs
Sui BCS Course: https://github.com/sui-foundation/sui-move-intro-course/blob/main/advanced-topics/BCS_encoding

Key principles:
- All integers are little-endian
- Strings are vectors of u8s: uleb128 length + UTF-8 bytes
- Vectors are uleb128 length + concatenated encoded elements
- Structs are encoded by field order (no type tags in BCS itself for regular structs)
"""

import struct
from typing import Union, List, Any


# ─────────────────────────────────────────────────────────────────────────────
# Primitive Types
# ─────────────────────────────────────────────────────────────────────────────


def encode_u8(value: int) -> bytes:
    """Encode a u8 (unsigned 8-bit integer).

    Args:
        value: Integer 0-255

    Returns:
        1 byte
    """
    if not 0 <= value <= 255:
        raise ValueError(f"u8 out of range: {value}")
    return bytes([value])


def encode_u16(value: int) -> bytes:
    """Encode a u16 (unsigned 16-bit integer) in little-endian.

    Args:
        value: Integer 0-65535

    Returns:
        2 bytes, little-endian
    """
    if not 0 <= value <= 65535:
        raise ValueError(f"u16 out of range: {value}")
    return struct.pack('<H', value)


def encode_u32(value: int) -> bytes:
    """Encode a u32 (unsigned 32-bit integer) in little-endian.

    Args:
        value: Integer 0-4294967295

    Returns:
        4 bytes, little-endian
    """
    if not 0 <= value <= 4294967295:
        raise ValueError(f"u32 out of range: {value}")
    return struct.pack('<I', value)


def encode_u64(value: int) -> bytes:
    """Encode a u64 (unsigned 64-bit integer) in little-endian.

    Args:
        value: Integer 0-18446744073709551615

    Returns:
        8 bytes, little-endian
    """
    if not 0 <= value <= 18446744073709551615:
        raise ValueError(f"u64 out of range: {value}")
    return struct.pack('<Q', value)


def encode_u128(value: int) -> bytes:
    """Encode a u128 (unsigned 128-bit integer) in little-endian.

    Args:
        value: Large integer (0-2^128-1)

    Returns:
        16 bytes, little-endian
    """
    if not 0 <= value <= (2**128 - 1):
        raise ValueError(f"u128 out of range: {value}")
    return struct.pack('<QQ', value & 0xFFFFFFFFFFFFFFFF, (value >> 64) & 0xFFFFFFFFFFFFFFFF)


def encode_bool(value: bool) -> bytes:
    """Encode a boolean as u8 (0 or 1).

    Args:
        value: True or False

    Returns:
        1 byte: 0x00 or 0x01
    """
    return bytes([1 if value else 0])


# ─────────────────────────────────────────────────────────────────────────────
# Variable-Length Encoding
# ─────────────────────────────────────────────────────────────────────────────


def encode_uleb128(value: int) -> bytes:
    """Encode an unsigned integer using ULEB128 (variable-length encoding).

    Used for: vector/string lengths, option discriminants
    ULEB128 encodes in 7-bit chunks with continuation bit.

    Args:
        value: Non-negative integer

    Returns:
        1-5 bytes (depending on magnitude)
    """
    if value < 0:
        raise ValueError(f"ULEB128 requires non-negative value: {value}")

    result = []
    while value >= 0x80:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value & 0x7F)
    return bytes(result)


# ─────────────────────────────────────────────────────────────────────────────
# Strings and Vectors
# ─────────────────────────────────────────────────────────────────────────────


def encode_string(value: str) -> bytes:
    """Encode a String (UTF-8 text) in BCS format.

    Format: uleb128(length) + UTF-8 bytes

    Args:
        value: UTF-8 string

    Returns:
        ULEB128 length + encoded UTF-8
    """
    utf8_bytes = value.encode('utf-8')
    return encode_uleb128(len(utf8_bytes)) + utf8_bytes


def encode_bytes(value: bytes) -> bytes:
    """Encode raw bytes as a vector of u8s.

    Format: uleb128(length) + raw bytes

    Args:
        value: Raw byte string

    Returns:
        ULEB128 length + bytes
    """
    return encode_uleb128(len(value)) + value


def encode_vector(values: List[bytes]) -> bytes:
    """Encode a vector of pre-encoded elements.

    Format: uleb128(count) + concatenated encoded elements

    Args:
        values: List of already-encoded byte strings

    Returns:
        ULEB128 length + concatenated elements
    """
    return encode_uleb128(len(values)) + b''.join(values)


# ─────────────────────────────────────────────────────────────────────────────
# Address and ID Types
# ─────────────────────────────────────────────────────────────────────────────


def encode_address(address: str) -> bytes:
    """Encode a Sui address (32 bytes).

    Expects: hex string with or without '0x' prefix

    Args:
        address: Hex string like '0xabcd...' or 'abcd...'

    Returns:
        32 bytes
    """
    # Remove 0x prefix if present
    if address.startswith('0x') or address.startswith('0x'):
        address = address[2:]

    # Pad to 64 hex chars (32 bytes)
    address = address.zfill(64)

    if len(address) != 64:
        raise ValueError(f"Address must be 32 bytes (64 hex chars): {address}")

    return bytes.fromhex(address)


def decode_address(data: bytes) -> str:
    """Decode a 32-byte address to hex string.

    Args:
        data: 32 bytes

    Returns:
        Hex string with '0x' prefix
    """
    if len(data) != 32:
        raise ValueError(f"Address must be 32 bytes: {len(data)}")
    return '0x' + data.hex()


# ─────────────────────────────────────────────────────────────────────────────
# Complex Types
# ─────────────────────────────────────────────────────────────────────────────


def encode_option(value: Union[bytes, None]) -> bytes:
    """Encode an Option<T> (Some(T) or None).

    Format:
      - 0x00 for None
      - 0x01 + encoded(T) for Some(T)

    Args:
        value: Pre-encoded T, or None

    Returns:
        1 byte (0x00 or 0x01) + optional encoded value
    """
    if value is None:
        return bytes([0x00])
    else:
        return bytes([0x01]) + value


def encode_struct(fields: List[bytes], type_tag: str = None) -> bytes:
    """Encode a Move struct.

    Note: BCS itself doesn't include type tags in the encoded data. Type tags are
    only used in the Sui native hash_type_and_key function for collision prevention.

    Encoding is simply: concatenated encoded fields in declaration order.

    Args:
        fields: List of pre-encoded field values (in declaration order)
        type_tag: Optional full type path (used in hash_type_and_key, not in encoding)

    Returns:
        Concatenated encoded fields
    """
    return b''.join(fields)


# ─────────────────────────────────────────────────────────────────────────────
# Sui-Specific Helpers
# ─────────────────────────────────────────────────────────────────────────────


def encode_type_tag(type_path: str) -> bytes:
    """Encode a Move type tag as a string (used in hash_type_and_key).

    The type tag is encoded as a String: uleb128(length) + UTF-8 bytes.
    This is used by Sui's native hash_type_and_key function to prevent collisions.

    Args:
        type_path: Full type path like "0x...::module::Type<0x...::NestedType>"

    Returns:
        Encoded type string
    """
    return encode_string(type_path)


def hash_input_for_derived_object(
    parent_address: str,
    key_encoded: bytes,
    type_tag: str
) -> bytes:
    """Prepare hash input for Sui's hash_type_and_key function.

    This combines the parent address, key data, and type information in the format
    expected by Sui's native hash_type_and_key function.

    Args:
        parent_address: Parent object address (hex with or without 0x prefix)
        key_encoded: Pre-encoded key data (BCS-encoded TenantItemId or similar)
        type_tag: Full type path for the DerivedObjectKey wrapper

    Returns:
        Concatenated: parent_address_bytes || key_encoded || type_encoded

    Note:
        This is NOT the exact formula - it's a best guess based on Sui's pattern.
        The actual native function implementation may differ.
        Testing against known values is required to verify correctness.
    """
    parent_bytes = encode_address(parent_address)
    type_bytes = encode_type_tag(type_tag)

    # Pattern hypothesis: parent || key || type (like dynamic fields)
    return parent_bytes + key_encoded + type_bytes


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────


def bytes_to_hex(data: bytes) -> str:
    """Convert bytes to lowercase hex string with 0x prefix."""
    return '0x' + data.hex()


def hex_to_bytes(hex_str: str) -> bytes:
    """Convert hex string (with or without 0x) to bytes."""
    if hex_str.startswith('0x') or hex_str.startswith('0x'):
        hex_str = hex_str[2:]
    return bytes.fromhex(hex_str)
