#pragma once
#include <string>
#include <functional>

namespace http {
    // Posts a JSON body to the companion chat endpoint.
    // Runs synchronously — call from a background thread.
    // onChunk: called for each SSE text chunk as it arrives.
    // onDone:  called when server sends [DONE].
    // Returns false on connection or HTTP error; sets errorOut.
    bool postChat(
        const std::string& jsonBody,
        std::function<void(const std::string& chunk)> onChunk,
        std::function<void()> onDone,
        std::string& errorOut);
}
