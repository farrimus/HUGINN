#pragma once
// Phase 3 stub — shared memory IPC
// Full implementation deferred to Phase 3 (state channel + event queue).
// Included here so overlay_core can reference the type without compile errors.

#include "schema.h"
#include <string_view>

namespace shm {

// Phase 3: open or create the named shared memory segment.
// Returns nullptr until Phase 3 is implemented.
inline SharedHeader* open(std::wstring_view name) {
    (void)name;
    return nullptr;
}

inline void close(SharedHeader* /*ptr*/) {}

} // namespace shm
