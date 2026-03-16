#include "render.h"
#include "companion_panel.h"
#include "route_panel.h"
#include "ship_profile_panel.h"

namespace ui {

bool visible = true;

void init() {
    route_panel::init();
    ship_profile_panel::init();
}

void shutdown() {
    route_panel::shutdown();
    ship_profile_panel::shutdown();
}

void renderImGui() {
    if (!visible) return;
    companion_panel::draw();
    route_panel::draw();
    ship_profile_panel::draw();
}

} // namespace ui
