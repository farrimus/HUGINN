#include "render.h"
#include "companion_panel.h"
#include "route_panel.h"

namespace ui {

// Overlay visibility — toggled by F8 in input.cpp
bool visible = true;

void init() {
    route_panel::init();
}

void shutdown() {
    route_panel::shutdown();
}

void renderImGui() {
    if (!visible) return;
    companion_panel::draw();
    route_panel::draw();
}

} // namespace ui
