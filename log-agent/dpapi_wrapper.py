import sys
import base64

if sys.platform == "win32":
    try:
        import ctypes

        def encrypt_data(plaintext: str) -> str:
            """Encrypt plaintext using Windows DPAPI."""
            plaintext_bytes = plaintext.encode("utf-8")
            ciphertext = ctypes.windll.crypt32.CryptProtectData(
                ctypes.create_string_buffer(plaintext_bytes),
                None, None, None,
                None, 1, None
            )
            # Return as base64 for storage
            return base64.b64encode(ciphertext).decode("utf-8")

        def decrypt_data(ciphertext_b64: str) -> str:
            """Decrypt ciphertext using Windows DPAPI."""
            ciphertext = base64.b64decode(ciphertext_b64)
            plaintext = ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.create_string_buffer(ciphertext),
                None, None, None,
                None, 1, None
            )
            return plaintext.decode("utf-8")

    except Exception:
        raise ImportError("DPAPI not available on this Windows version")
else:
    raise ImportError("DPAPI only available on Windows")
