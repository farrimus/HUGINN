#pragma once

namespace route_panel {
    // Initialize background polling thread (call once at startup).
    void init();
    // Draw the route panel. Call each frame when overlay is visible.
    void draw();
    // Stop the background polling thread (call at shutdown).
    void shutdown();
}
