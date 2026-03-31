r"""
Test suite for Sui address format validation and path traversal protection.

This module validates that:
1. Valid Sui addresses (0x + 64 hex chars) pass through validators
2. Invalid addresses (wrong length, missing 0x, non-hex) are rejected
3. Path traversal attempts (backslash, forward slash, .., :, etc.) are blocked
4. Windows escape sequences and control characters are blocked
5. Memory store _pilot_path() enforces strict validation
"""

import pytest
from pydantic import ValidationError

# Import classes from main.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import VerifyRequest, DealClaimRequest
from src.memory_store import MemoryStore


# Valid test addresses
VALID_SUI_ADDRESS = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
VALID_SUI_ADDRESS_UPPERCASE = "0xABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789"
VALID_SUI_ADDRESS_MIXED = "0xAbCdEf0123456789AbCdEf0123456789AbCdEf0123456789AbCdEf0123456789"


class TestVerifyRequestValidation:
    """Test VerifyRequest address field validation."""

    def test_valid_address_lowercase(self):
        """Valid lowercase Sui address should pass."""
        req = VerifyRequest(
            address=VALID_SUI_ADDRESS,
            signature="sig",
            nonce="nonce",
            structure_id="keep-7a"
        )
        assert req.address == VALID_SUI_ADDRESS

    def test_valid_address_uppercase_normalized_to_lowercase(self):
        """Valid uppercase address should be normalized to lowercase."""
        req = VerifyRequest(
            address=VALID_SUI_ADDRESS_UPPERCASE,
            signature="sig",
            nonce="nonce",
            structure_id="keep-7a"
        )
        assert req.address == VALID_SUI_ADDRESS_UPPERCASE.lower()

    def test_valid_address_mixed_case_normalized(self):
        """Mixed case address should be normalized to lowercase."""
        req = VerifyRequest(
            address=VALID_SUI_ADDRESS_MIXED,
            signature="sig",
            nonce="nonce",
            structure_id="keep-7a"
        )
        assert req.address == VALID_SUI_ADDRESS_MIXED.lower()

    def test_missing_0x_prefix(self):
        """Address without 0x prefix should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VerifyRequest(
                address="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                signature="sig",
                nonce="nonce",
                structure_id="keep-7a"
            )
        assert "must be 0x followed by 64 hexadecimal characters" in str(exc_info.value)

    def test_too_short_address(self):
        """Address shorter than 66 characters should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VerifyRequest(
                address="0x1234567890abcdef",
                signature="sig",
                nonce="nonce",
                structure_id="keep-7a"
            )
        assert "must be 0x followed by 64 hexadecimal characters" in str(exc_info.value)

    def test_too_long_address(self):
        """Address longer than 66 characters should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VerifyRequest(
                address="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef00",
                signature="sig",
                nonce="nonce",
                structure_id="keep-7a"
            )
        assert "must be 0x followed by 64 hexadecimal characters" in str(exc_info.value)

    def test_non_hexadecimal_characters(self):
        """Non-hexadecimal characters should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VerifyRequest(
                address="0xZZZZZZZZ90abcdefZZZZZZZZ90abcdefZZZZZZZZ90abcdefZZZZZZZZ90abcdef",
                signature="sig",
                nonce="nonce",
                structure_id="keep-7a"
            )
        assert "contains non-hexadecimal characters" in str(exc_info.value)

    def test_backslash_path_traversal(self):
        """Backslash for Windows path traversal should be rejected by validator."""
        # Backslash is not a hex character, fails hex validation
        with pytest.raises(ValidationError) as exc_info:
            VerifyRequest(
                address="0x1234567890abcdef\\1234567890abcdef1234567890abcdef1234567890abcd",
                signature="sig",
                nonce="nonce",
                structure_id="keep-7a"
            )
        # Should fail on hex validation (backslash is not hex)
        error_str = str(exc_info.value).lower()
        assert "hexadecimal" in error_str or "characters" in error_str

    def test_forward_slash_traversal(self):
        """Forward slash for path traversal should be rejected by validator."""
        # Forward slash is not a hex character
        with pytest.raises(ValidationError) as exc_info:
            VerifyRequest(
                address="0x1234567890abcdef/1234567890abcdef1234567890abcdef1234567890abcd",
                signature="sig",
                nonce="nonce",
                structure_id="keep-7a"
            )
        error_str = str(exc_info.value).lower()
        assert "hexadecimal" in error_str or "characters" in error_str

    def test_double_dot_traversal(self):
        """Double dots (..) for path traversal should be rejected by validator."""
        # Dots are not valid in the hex part
        with pytest.raises(ValidationError) as exc_info:
            VerifyRequest(
                address="0x1234567890abcdef..1234567890abcdef1234567890abcdef1234567890abc",
                signature="sig",
                nonce="nonce",
                structure_id="keep-7a"
            )
        error_str = str(exc_info.value).lower()
        assert "hexadecimal" in error_str or "characters" in error_str

    def test_empty_address(self):
        """Empty address should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            VerifyRequest(
                address="",
                signature="sig",
                nonce="nonce",
                structure_id="keep-7a"
            )
        assert "must be 0x followed by 64 hexadecimal characters" in str(exc_info.value)

    def test_none_address(self):
        """None address should be rejected."""
        with pytest.raises((ValidationError, TypeError)):
            VerifyRequest(
                address=None,
                signature="sig",
                nonce="nonce",
                structure_id="keep-7a"
            )


class TestDealClaimRequestValidation:
    """Test DealClaimRequest address field validation."""

    def test_valid_address_lowercase(self):
        """Valid lowercase Sui address should pass."""
        req = DealClaimRequest(
            nonce="nonce",
            address=VALID_SUI_ADDRESS,
            structure_id="keep-7a",
            signature="sig",
            payment_method="sui"
        )
        assert req.address == VALID_SUI_ADDRESS

    def test_valid_address_uppercase_normalized(self):
        """Valid uppercase address should be normalized to lowercase."""
        req = DealClaimRequest(
            nonce="nonce",
            address=VALID_SUI_ADDRESS_UPPERCASE,
            structure_id="keep-7a",
            signature="sig",
            payment_method="sui"
        )
        assert req.address == VALID_SUI_ADDRESS_UPPERCASE.lower()

    def test_missing_0x_prefix(self):
        """Address without 0x prefix should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DealClaimRequest(
                nonce="nonce",
                address="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                structure_id="keep-7a",
                signature="sig",
                payment_method="sui"
            )
        assert "must be 0x followed by 64 hexadecimal characters" in str(exc_info.value)

    def test_non_hexadecimal_characters(self):
        """Non-hexadecimal characters should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DealClaimRequest(
                nonce="nonce",
                address="0xGGGGGGGG90abcdefGGGGGGGG90abcdefGGGGGGGG90abcdefGGGGGGGG90abcdef",
                structure_id="keep-7a",
                signature="sig",
                payment_method="sui"
            )
        assert "contains non-hexadecimal characters" in str(exc_info.value)

    def test_colon_escape_sequence(self):
        """Colon for Windows drive letter attack should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DealClaimRequest(
                nonce="nonce",
                address="0x1234567890abcdef:1234567890abcdef1234567890abcdef1234567890abcd",
                structure_id="keep-7a",
                signature="sig",
                payment_method="sui"
            )
        error_str = str(exc_info.value).lower()
        assert "hexadecimal" in error_str or "characters" in error_str


class TestMemoryStorePathValidation:
    """Test memory store _pilot_path() strict address validation."""

    @pytest.fixture
    def memory_store(self, tmp_path):
        """Create a MemoryStore instance with temporary directory."""
        return MemoryStore(base_dir=str(tmp_path), structure_id="test-structure")

    def test_valid_address_path(self, memory_store):
        """Valid address should produce a safe file path."""
        path = memory_store._pilot_path(VALID_SUI_ADDRESS)
        assert path.endswith(f"{VALID_SUI_ADDRESS.lower()}.json")
        assert ".." not in path
        assert "\\" not in path

    def test_valid_address_uppercase_normalized_in_path(self, memory_store):
        """Uppercase address should be normalized in path."""
        path = memory_store._pilot_path(VALID_SUI_ADDRESS_UPPERCASE)
        assert VALID_SUI_ADDRESS_UPPERCASE.lower() in path
        assert VALID_SUI_ADDRESS_UPPERCASE not in path

    def test_rejects_backslash(self, memory_store):
        """Backslash in address should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory_store._pilot_path("0x123456789abcdef\\12345678901234567890abcdef1234567890abcd")
        error_str = str(exc_info.value)
        assert "forbidden character sequence" in error_str or "hexadecimal" in error_str

    def test_rejects_forward_slash(self, memory_store):
        """Forward slash in address should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory_store._pilot_path("0x12345678901234567890abcdef/123456789012345678901234567890abc")
        error_str = str(exc_info.value)
        assert "forbidden character sequence" in error_str or "hexadecimal" in error_str

    def test_rejects_double_dot(self, memory_store):
        """Double dot (..) in address should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory_store._pilot_path("0x123456789012345678901234567890..1234567890123456789012345678")
        error_str = str(exc_info.value)
        assert "forbidden character sequence" in error_str or "hexadecimal" in error_str

    def test_rejects_colon(self, memory_store):
        """Colon in address should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory_store._pilot_path("0x123456789012345678901234567890:123456789012345678901234567890")
        error_str = str(exc_info.value)
        assert "forbidden character sequence" in error_str or "hexadecimal" in error_str

    def test_rejects_single_dot(self, memory_store):
        """Single dot in address should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory_store._pilot_path("0x1234567890123456789012345678901.234567890123456789012345678901")
        error_str = str(exc_info.value)
        assert "forbidden character sequence" in error_str or "hexadecimal" in error_str

    def test_rejects_null_byte(self, memory_store):
        """Null byte in address should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory_store._pilot_path("0x12345678901234567890123456789\x001234567890123456789012345678901")
        error_str = str(exc_info.value)
        assert "forbidden character sequence" in error_str or "characters" in error_str

    def test_rejects_tab_character(self, memory_store):
        """Tab character in address should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory_store._pilot_path("0x1234567890123456789012345678901\t234567890123456789012345678901")
        error_str = str(exc_info.value)
        assert "forbidden character sequence" in error_str or "characters" in error_str

    def test_rejects_newline_character(self, memory_store):
        """Newline character in address should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory_store._pilot_path("0x1234567890123456789012345678901\n234567890123456789012345678901")
        error_str = str(exc_info.value)
        assert "forbidden character sequence" in error_str or "characters" in error_str

    def test_rejects_carriage_return(self, memory_store):
        """Carriage return in address should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory_store._pilot_path("0x1234567890123456789012345678901\r234567890123456789012345678901")
        error_str = str(exc_info.value)
        assert "forbidden character sequence" in error_str or "characters" in error_str

    def test_rejects_short_address(self, memory_store):
        """Address shorter than 66 characters should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory_store._pilot_path("0x1234567890abcdef")
        assert "must be 0x followed by 64 hexadecimal characters" in str(exc_info.value)

    def test_rejects_long_address(self, memory_store):
        """Address longer than 66 characters should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory_store._pilot_path("0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef00")
        assert "must be 0x followed by 64 hexadecimal characters" in str(exc_info.value)

    def test_rejects_missing_0x(self, memory_store):
        """Address without 0x prefix should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory_store._pilot_path("1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef")
        assert "must be 0x followed by 64 hexadecimal characters" in str(exc_info.value)

    def test_rejects_non_hex_characters(self, memory_store):
        """Non-hexadecimal characters should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory_store._pilot_path("0xZZZZZZZZ90abcdefZZZZZZZZ90abcdefZZZZZZZZ90abcdefZZZZZZZZ90abcdef")
        assert "contains non-hexadecimal characters" in str(exc_info.value)

    def test_rejects_empty_address(self, memory_store):
        """Empty address should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            memory_store._pilot_path("")
        assert "must be 0x followed by 64 hexadecimal characters" in str(exc_info.value)

    def test_rejects_none_address(self, memory_store):
        """None address should be rejected."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            memory_store._pilot_path(None)


class TestWindowsEscapeSequences:
    """Test rejection of Windows-specific escape sequences."""

    def test_unc_path_escape(self):
        """UNC path escape (\\\\server) should be rejected."""
        with pytest.raises(ValidationError):
            VerifyRequest(
                address="0x\\\\server\\share1234567890abcdef1234567890abcdef1234567890",
                signature="sig",
                nonce="nonce",
                structure_id="keep-7a"
            )

    def test_drive_letter_escape(self):
        """Drive letter escape (C:) should be rejected."""
        with pytest.raises(ValidationError):
            VerifyRequest(
                address="0xC:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcd",
                signature="sig",
                nonce="nonce",
                structure_id="keep-7a"
            )


class TestAddressIntegration:
    """Integration tests combining main.py validators and memory_store."""

    @pytest.fixture
    def memory_store(self, tmp_path):
        """Create a MemoryStore instance."""
        return MemoryStore(base_dir=str(tmp_path), structure_id="test-structure")

    def test_valid_request_address_in_memory_store(self, memory_store):
        """Valid address from VerifyRequest should work with memory_store._pilot_path()."""
        req = VerifyRequest(
            address=VALID_SUI_ADDRESS,
            signature="sig",
            nonce="nonce",
            structure_id="keep-7a"
        )
        # The request normalized the address to lowercase
        path = memory_store._pilot_path(req.address)
        assert VALID_SUI_ADDRESS.lower() in path
        assert path.endswith(".json")

    def test_normalized_address_consistency(self, memory_store):
        """Uppercase address normalized by validator should work in memory_store."""
        req = VerifyRequest(
            address=VALID_SUI_ADDRESS_UPPERCASE,
            signature="sig",
            nonce="nonce",
            structure_id="keep-7a"
        )
        # Both should produce the same normalized path
        path = memory_store._pilot_path(req.address)
        expected_lower = VALID_SUI_ADDRESS_UPPERCASE.lower()
        assert expected_lower in path
