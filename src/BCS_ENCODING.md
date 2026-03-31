# BCS Encoding Module

Binary Canonical Serialization (BCS) encoding for Sui Move types.

## Overview

This module provides utilities for encoding Move data types to bytes in BCS format, following Sui's specification. BCS is the standard serialization format used throughout the Sui blockchain.

## Why BCS?

Sui uses BCS to serialize Move structs, vectors, and primitives. The `hash_type_and_key` native function (used for derived objects) requires properly BCS-encoded input. Manual byte concatenation won't work—the encoding must follow Sui's exact rules.

## Core Principles

- **Little-endian integers** — All integer types (u8, u16, u32, u64, u128) are encoded as little-endian bytes
- **ULEB128 lengths** — Vector/string lengths use variable-length encoding for compactness
- **Field order** — Struct fields are encoded in declaration order
- **Type information** — Type paths are encoded as strings and included in hash computations for collision prevention

## Usage Examples

### Basic Types

```python
from src.bcs_encoding import *

# Integers (little-endian)
encode_u8(42)              # b'*'
encode_u64(2112000113)     # b'\x71\x90\xe2\x7d\x00\x00\x00\x00'

# Boolean
encode_bool(True)          # b'\x01'
encode_bool(False)         # b'\x00'

# Strings (ULEB128 length + UTF-8)
encode_string("hello")     # b'\x05hello'
encode_string("utopia")    # b'\x06utopia'
```

### Structures

```python
# Encoding a TenantItemId struct: { item_id: u64, tenant: String }
fields = [
    encode_u64(2112000113),
    encode_string("utopia")
]
encoded = encode_struct(fields)
# Output: b'\x71\x90\xe2\x7d\x00\x00\x00\x00\x06utopia'
```

### Addresses

```python
# Sui addresses (32 bytes)
addr = "0xc2b969a72046c47e24991d69472afb2216af9e91caf802684514f39706d7dc57"
encoded = encode_address(addr)      # 32 bytes
decoded = decode_address(encoded)   # hex string with 0x prefix
```

### Type Tags (for hash_type_and_key)

```python
# Type tags are encoded as strings
type_tag = "0x...::object_registry::DerivedObjectKey<0x...::object_registry::TenantItemId>"
encoded = encode_type_tag(type_tag)

# This is part of the hash input for derived object address derivation
```

## ULEB128 Encoding

ULEB128 (unsigned little-endian base-128) is used for variable-length integers.

```python
encode_uleb128(0)      # b'\x00' (single byte for 0-127)
encode_uleb128(127)    # b'\x7f'
encode_uleb128(128)    # b'\x80\x01' (two bytes, continuation bit set)
encode_uleb128(16384)  # b'\x80\x80\x01' (three bytes)
```

Why ULEB128? Saves space for small values (strings/vectors with <128 elements use 1 byte for length instead of 4).

## Testing

All encoding functions are tested against:
- Known BCS vectors from Sui SDK
- EVE Frontier values (TenantItemId struct)
- Edge cases (empty strings, maximum values, padding)

Run tests:
```bash
python3 -m pytest tests/test_bcs_encoding.py -v
```

## Key Encodings for Derived Objects

When deriving a StorageUnit address, three components are encoded:

1. **Parent Address** (32 bytes)
   ```python
   parent_bytes = encode_address("0xc2b9...")
   ```

2. **Key Struct** (TenantItemId)
   ```python
   key_bytes = encode_struct([
       encode_u64(2112000113),    # item_id
       encode_string("utopia")     # tenant
   ])
   ```

3. **Type Tag** (DerivedObjectKey wrapper)
   ```python
   type_bytes = encode_type_tag("0x...::DerivedObjectKey<0x...::TenantItemId>")
   ```

The `hash_input_for_derived_object` helper combines these:
```python
hash_input = hash_input_for_derived_object(
    parent_address="0xc2b9...",
    key_encoded=key_bytes,
    type_tag="0x...::DerivedObjectKey<0x...::TenantItemId>"
)
```

Then BLAKE2b-256 hash the input to get the derived address.

## Limitations

- This module handles BCS encoding, not decoding (yet)
- The `hash_input_for_derived_object` function contains a **hypothesis** about byte order:
  - Current: `parent || key || type`
  - Needs verification against known on-chain values
- Some Move types not yet implemented (maps, tables, advanced generics)

## References

- [BCS Specification](https://github.com/MystenLabs/bcs)
- [Sui BCS Course](https://github.com/sui-foundation/sui-move-intro-course/blob/main/advanced-topics/BCS_encoding)
- [Sui Move Intro Course](https://github.com/sui-foundation/sui-move-intro-course)
- [Sui Derived Objects](https://docs.sui.io/concepts/sui-move-concepts/derived-objects)
