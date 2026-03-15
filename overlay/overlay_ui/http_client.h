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

    // GET request — returns full response body in bodyOut.
    // Runs synchronously — call from a background thread.
    // Returns false on connection or HTTP error; sets errorOut.
    bool getJson(
        const std::string& path,
        std::string& bodyOut,
        std::string& errorOut);

    // POST with no body (fire-and-forget style).
    // Returns false on connection or HTTP error; sets errorOut.
    bool postEmpty(
        const std::string& path,
        std::string& errorOut);
}
