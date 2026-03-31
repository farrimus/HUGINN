"""
Tests for BCS encoding module.

Validates that all encoding functions produce correct bytes according to
Sui's BCS specification.
"""

import pytest
from src.bcs_encoding import (
    encode_u8, encode_u16, encode_u32, encode_u64, encode_u128,
    encode_bool, encode_uleb128,
    encode_string, encode_bytes, encode_vector,
    encode_address, decode_address,
    encode_option, encode_struct,
    encode_type_tag, hash_input_for_derived_object,
    bytes_to_hex, hex_to_bytes
)


# ─────────────────────────────────────────────────────────────────────────────
# Primitive Type Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegerEncoding:
    """Test integer encoding (all little-endian)."""

    def test_encode_u8(self):
        assert encode_u8(0) == b'\x00'
        assert encode_u8(255) == b'\xff'
        assert encode_u8(127) == b'\x7f'

    def test_encode_u8_out_of_range(self):
        with pytest.raises(ValueError):
            encode_u8(256)
        with pytest.raises(ValueError):
            encode_u8(-1)

    def test_encode_u16(self):
        # Little-endian: 0x0100 = 256 → bytes [0x00, 0x01]
        assert encode_u16(256) == b'\x00\x01'
        assert encode_u16(0) == b'\x00\x00'
        assert encode_u16(65535) == b'\xff\xff'

    def test_encode_u32(self):
        # Little-endian: 0x01000000 = 16777216 → bytes [0x00, 0x00, 0x00, 0x01]
        assert encode_u32(16777216) == b'\x00\x00\x00\x01'
        assert encode_u32(0) == b'\x00\x00\x00\x00'

    def test_encode_u64(self):
        # Little-endian: 0x0100000000000000 = 72057594037927936 → 8 bytes [0x00]*7 + [0x01]
        assert encode_u64(72057594037927936) == b'\x00\x00\x00\x00\x00\x00\x00\x01'
        assert encode_u64(0) == b'\x00\x00\x00\x00\x00\x00\x00\x00'
        # Test a known value from EVE (2112000113 in little-endian)
        assert encode_u64(2112000113) == b'\x71\x90\xe2\x7d\x00\x00\x00\x00'

    def test_encode_u128(self):
        assert encode_u128(0) == b'\x00' * 16
        assert len(encode_u128(2**127)) == 16


class TestBooleanEncoding:
    """Test boolean encoding."""

    def test_encode_bool(self):
        assert encode_bool(True) == b'\x01'
        assert encode_bool(False) == b'\x00'


# ─────────────────────────────────────────────────────────────────────────────
# Variable-Length Encoding Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestULEB128:
    """Test ULEB128 variable-length encoding."""

    def test_single_byte_values(self):
        # Values 0-127 encode to single byte
        assert encode_uleb128(0) == b'\x00'
        assert encode_uleb128(127) == b'\x7f'

    def test_multi_byte_values(self):
        # 128 = 0x80 → requires 2 bytes: 0x80, 0x01
        assert encode_uleb128(128) == b'\x80\x01'
        # 255 = 0xff → 0xff, 0x01
        assert encode_uleb128(255) == b'\xff\x01'
        # 16384 = 0x4000 → 0x80, 0x80, 0x01
        assert encode_uleb128(16384) == b'\x80\x80\x01'

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            encode_uleb128(-1)


# ─────────────────────────────────────────────────────────────────────────────
# String and Vector Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestStringEncoding:
    """Test string encoding (uleb128 length + UTF-8)."""

    def test_empty_string(self):
        # Empty: length 0 (encoded as 0x00) + no bytes
        assert encode_string("") == b'\x00'

    def test_simple_string(self):
        # "hello" = 5 bytes
        result = encode_string("hello")
        assert result == b'\x05hello'

    def test_string_with_length_prefix(self):
        # Length is encoded as ULEB128
        text = "a" * 128
        result = encode_string(text)
        assert result[0:2] == b'\x80\x01'  # Length 128 in ULEB128
        assert result[2:] == b'a' * 128

    def test_unicode_string(self):
        # UTF-8 encoding is multi-byte
        text = "hello🚀"  # rocket emoji is 4 bytes in UTF-8
        result = encode_string(text)
        utf8_bytes = text.encode('utf-8')
        assert result == encode_uleb128(len(utf8_bytes)) + utf8_bytes


class TestBytesEncoding:
    """Test raw bytes encoding (uleb128 length + bytes)."""

    def test_empty_bytes(self):
        assert encode_bytes(b'') == b'\x00'

    def test_simple_bytes(self):
        assert encode_bytes(b'\x01\x02\x03') == b'\x03\x01\x02\x03'


class TestVectorEncoding:
    """Test vector encoding (uleb128 count + elements)."""

    def test_empty_vector(self):
        assert encode_vector([]) == b'\x00'

    def test_vector_of_bytes(self):
        # Vector of 3 u8 values: [1, 2, 3]
        elements = [b'\x01', b'\x02', b'\x03']
        result = encode_vector(elements)
        # Length 3 (0x03) + concatenated bytes
        assert result == b'\x03\x01\x02\x03'


# ─────────────────────────────────────────────────────────────────────────────
# Address Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAddressEncoding:
    """Test Sui address encoding (32 bytes)."""

    def test_address_with_0x_prefix(self):
        addr = "0x" + "ab" * 32  # 64 hex chars
        result = encode_address(addr)
        assert len(result) == 32
        assert result == bytes.fromhex("ab" * 32)

    def test_address_without_prefix(self):
        addr = "ab" * 32
        result = encode_address(addr)
        assert len(result) == 32

    def test_address_short_padded_left(self):
        # Short address should pad with zeros on the left
        addr = "0x1"
        result = encode_address(addr)
        assert len(result) == 32
        assert result == b'\x00' * 31 + b'\x01'

    def test_address_decode(self):
        original = "0x" + "ab" * 32
        data = encode_address(original)
        decoded = decode_address(data)
        assert decoded.lower() == original.lower()

    def test_short_address_padded(self):
        # Short addresses are left-padded with zeros
        result = encode_address("0x1234")
        assert len(result) == 32
        # 0x1234 → padded to 64 hex chars (62 zeros + 1234) → encoded as 32 bytes
        assert result == b'\x00' * 30 + b'\x12\x34'


# ─────────────────────────────────────────────────────────────────────────────
# Option Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestOptionEncoding:
    """Test Option<T> encoding."""

    def test_option_none(self):
        assert encode_option(None) == b'\x00'

    def test_option_some(self):
        value = b'\x42'
        result = encode_option(value)
        assert result == b'\x01\x42'


# ─────────────────────────────────────────────────────────────────────────────
# Struct Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestStructEncoding:
    """Test Move struct encoding."""

    def test_empty_struct(self):
        # Struct with no fields
        assert encode_struct([]) == b''

    def test_struct_with_fields(self):
        # Struct with two u64 fields: {a: 1, b: 2}
        fields = [
            encode_u64(1),
            encode_u64(2)
        ]
        result = encode_struct(fields)
        assert result == encode_u64(1) + encode_u64(2)

    def test_struct_with_mixed_types(self):
        # Struct: {flag: true, count: 42, name: "test"}
        fields = [
            encode_bool(True),
            encode_u64(42),
            encode_string("test")
        ]
        result = encode_struct(fields)
        expected = encode_bool(True) + encode_u64(42) + encode_string("test")
        assert result == expected


# ─────────────────────────────────────────────────────────────────────────────
# Type Tag Encoding Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTypeTagEncoding:
    """Test type tag encoding (used in hash_type_and_key)."""

    def test_simple_type(self):
        type_tag = "u64"
        result = encode_type_tag(type_tag)
        assert result == encode_string("u64")

    def test_qualified_type(self):
        type_tag = "0x1::coin::Coin"
        result = encode_type_tag(type_tag)
        assert result == encode_string(type_tag)

    def test_generic_type(self):
        type_tag = "0x1::option::Option<0x2::simple_coin::SimpleCoin>"
        result = encode_type_tag(type_tag)
        assert result == encode_string(type_tag)


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests (TenantItemId Example)
# ─────────────────────────────────────────────────────────────────────────────


class TestTenantItemIdEncoding:
    """Test encoding of TenantItemId struct from EVE Frontier."""

    def test_encode_tenant_item_id(self):
        """
        TenantItemId { item_id: u64, tenant: String }

        Example: { item_id: 2112000113, tenant: "utopia" }
        """
        item_id = 2112000113
        tenant = "utopia"

        fields = [
            encode_u64(item_id),
            encode_string(tenant)
        ]
        result = encode_struct(fields)

        # Verify structure
        expected = encode_u64(2112000113) + encode_string("utopia")
        assert result == expected

        # Verify binary content
        assert result.startswith(b'\x71\x90\xe2\x7d')  # item_id in little-endian
        assert b'\x06utopia' in result  # length 6 + "utopia"


# ─────────────────────────────────────────────────────────────────────────────
# Utility Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestUtilities:
    """Test helper utilities."""

    def test_bytes_to_hex(self):
        data = b'\xab\xcd\xef'
        assert bytes_to_hex(data) == '0xabcdef'

    def test_hex_to_bytes(self):
        assert hex_to_bytes('0xabcdef') == b'\xab\xcd\xef'
        assert hex_to_bytes('abcdef') == b'\xab\xcd\xef'

    def test_round_trip(self):
        original = b'\x01\x02\x03\xff'
        hex_str = bytes_to_hex(original)
        recovered = hex_to_bytes(hex_str)
        assert recovered == original


# ─────────────────────────────────────────────────────────────────────────────
# Known Test Vectors
# ─────────────────────────────────────────────────────────────────────────────


class TestKnownVectors:
    """Test against known encoded values from Sui SDK or official sources."""

    def test_sui_address_all_zeros(self):
        """All-zero address should be 32 zero bytes."""
        addr = "0x" + "0" * 64
        result = encode_address(addr)
        assert result == b'\x00' * 32

    def test_sui_address_all_ones(self):
        """All-ones address should be 32 0xff bytes."""
        addr = "0x" + "f" * 64
        result = encode_address(addr)
        assert result == b'\xff' * 32


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
