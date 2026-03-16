#pragma once
namespace ship_profile_panel {
    void init();
    void draw();
    void shutdown();
    extern bool g_visible;  // toggled by F7; defined in ship_profile_panel.cpp
}
