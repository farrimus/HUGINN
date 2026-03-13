#include "render.h"
#include "companion_panel.h"

namespace ui {

// Overlay visibility — toggled by F8 in input.cpp
bool visible = true;

void renderImGui() {
    if (!visible) return;
    companion_panel::draw();
}

} // namespace ui
