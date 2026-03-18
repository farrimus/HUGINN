import sys
import base64
from ctypes import (
    Structure, c_char_p, c_uint32, POINTER, create_string_buffer,
    byref, windll, GetLastError, cast, c_char, string_at
)

if sys.platform == "win32":
    # Define DATA_BLOB structure for DPAPI
    class DATA_BLOB(Structure):
        _fields_ = [("cbData", c_uint32), ("pbData", POINTER(c_char_p))]

    def encrypt_data(plaintext: str) -> str:
        """Encrypt plaintext using Windows DPAPI.

        Args:
            plaintext: String to encrypt

        Returns:
            Base64-encoded encrypted data

        Raises:
            RuntimeError: If DPAPI encryption fails
        """
        plaintext_bytes = plaintext.encode("utf-8")

        # Create input blob
        input_data = create_string_buffer(plaintext_bytes)
        input_blob = DATA_BLOB()
        input_blob.cbData = len(plaintext_bytes)
        input_blob.pbData = cast(input_data, POINTER(c_char_p))

        # Create output blob (will be populated by CryptProtectData)
        output_blob = DATA_BLOB()

        # Call CryptProtectData
        success = windll.crypt32.CryptProtectData(
            byref(input_blob),
            None,  # Optional description (szDataDescr)
            None,  # Optional entropy (pOptionalEntropy)
            None,  # Reserved
            None,  # Prompt struct (pPromptStruct)
            1,     # Flags: CRYPTPROTECT_UI_FORBIDDEN
            byref(output_blob)  # Output buffer
        )

        if not success:
            error_code = GetLastError()
            raise RuntimeError(f"CryptProtectData failed with error code {error_code}")

        # Convert output to base64
        ciphertext = string_at(output_blob.pbData, output_blob.cbData)
        return base64.b64encode(ciphertext).decode("utf-8")

    def decrypt_data(ciphertext_b64: str) -> str:
        """Decrypt ciphertext using Windows DPAPI.

        Args:
            ciphertext_b64: Base64-encoded encrypted data

        Returns:
            Decrypted plaintext string

        Raises:
            RuntimeError: If DPAPI decryption fails
            ValueError: If input is not valid base64
        """
        try:
            ciphertext = base64.b64decode(ciphertext_b64)
        except Exception as e:
            raise ValueError(f"Invalid base64 input: {e}")

        # Create input blob
        input_data = create_string_buffer(ciphertext)
        input_blob = DATA_BLOB()
        input_blob.cbData = len(ciphertext)
        input_blob.pbData = cast(input_data, POINTER(c_char_p))

        # Create output blob (will be populated by CryptUnprotectData)
        output_blob = DATA_BLOB()

        # Call CryptUnprotectData
        success = windll.crypt32.CryptUnprotectData(
            byref(input_blob),
            None,  # Optional description output
            None,  # Optional entropy
            None,  # Reserved
            None,  # Prompt struct
            1,     # Flags
            byref(output_blob)  # Output buffer
        )

        if not success:
            error_code = GetLastError()
            raise RuntimeError(f"CryptUnprotectData failed with error code {error_code}")

        # Extract and decode plaintext
        plaintext_bytes = string_at(output_blob.pbData, output_blob.cbData)
        return plaintext_bytes.decode("utf-8")

else:
    raise ImportError("DPAPI only available on Windows")
