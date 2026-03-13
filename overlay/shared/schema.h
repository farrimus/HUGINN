#pragma once
#include <cstdint>

// Phase 3 stub — shared memory schema
// Magic: "EFOV" = 0x564F4645
// Matches Appendix A of EVE_FRONTIER_OVERLAY_ARCHITECTURE_HANDOFF.md

#pragma pack(push, 1)

constexpr uint32_t SCHEMA_MAGIC   = 0x564F4645; // "EFOV"
constexpr uint32_t SCHEMA_VERSION = 1;
constexpr uint32_t PAYLOAD_MAX    = 65536;

struct SharedHeader {
    uint32_t magic;
    uint32_t schema_version;
    uint32_t payload_size;
    uint8_t  payload[PAYLOAD_MAX];
};

#pragma pack(pop)
