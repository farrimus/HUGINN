#include "route_panel.h"
#include "http_client.h"
#include <imgui.h>
#include <string>
#include <vector>
#include <mutex>
#include <thread>
#include <atomic>
#include <nlohmann/json.hpp>

namespace route_panel {

// ---------------------------------------------------------------------------
// Shared state
// ---------------------------------------------------------------------------

struct RouteData {
    bool        active       = false;
    std::string origin;
    std::string destination;
    std::string path_str;       // formatted path line
    int         jumps        = 0;
    bool        has_error    = false;
    std::string error_msg;
    std::vector<std::string> warnings;
    std::vector<std::string> highlights;
};

static RouteData            s_route;
static std::mutex           s_mutex;
static std::atomic<bool>    s_running { false };
static std::thread          s_poller;
static bool                 s_clearing = false;

// ---------------------------------------------------------------------------
// Background polling (every 5 s)
// ---------------------------------------------------------------------------

static void _poll() {
    std::string body, err;
    if (!http::getJson("/current-route", body, err))
        return;

    try {
        auto j = nlohmann::json::parse(body);
        auto route = j["route"];

        std::lock_guard<std::mutex> lock(s_mutex);
        if (route.is_null()) {
            s_route = {};
            return;
        }

        s_route = {};
        s_route.active = true;

        if (route.contains("error") && !route["error"].is_null()) {
            s_route.has_error = true;
            s_route.error_msg = route["error"].get<std::string>();
            return;
        }

        auto path = route.value("path", nlohmann::json::array());
        s_route.jumps = route.value("jumps", 0);
        s_route.origin      = path.empty() ? "" : path.front().get<std::string>();
        s_route.destination = path.empty() ? "" : path.back().get<std::string>();

        // Format path: full if ≤5 hops, truncated otherwise
        if (path.size() > 5) {
            s_route.path_str =
                std::string(s_route.origin.c_str())
                + " -> [" + std::to_string((int)path.size() - 2) + " hops] -> "
                + std::string(s_route.destination.c_str());
        } else {
            s_route.path_str.clear();
            for (size_t i = 0; i < path.size(); ++i) {
                if (i > 0) s_route.path_str += " -> ";
                std::string sys = path[i].get<std::string>();
                for (auto& c : sys) c = (char)toupper((unsigned char)c);
                s_route.path_str += sys;
            }
        }

        s_route.warnings.clear();
        for (auto& w : route.value("warnings", nlohmann::json::array()))
            s_route.warnings.push_back(w.get<std::string>());

        s_route.highlights.clear();
        for (auto& h : route.value("highlights", nlohmann::json::array()))
            s_route.highlights.push_back(h.get<std::string>());

    } catch (...) { /* malformed JSON — skip */ }
}

static void _pollerThread() {
    while (s_running.load()) {
        _poll();
        // Sleep 5 s in 100 ms increments to stay responsive to shutdown
        for (int i = 0; i < 50 && s_running.load(); ++i)
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

void init() {
    s_running = true;
    s_poller = std::thread(_pollerThread);
}

void shutdown() {
    s_running = false;
    if (s_poller.joinable())
        s_poller.join();
}

// ---------------------------------------------------------------------------
// Draw
// ---------------------------------------------------------------------------

void draw() {
    ImGuiIO& io = ImGui::GetIO();

    const float panelW = 440.0f;
    const float panelH = 170.0f;
    const float margin = 16.0f;

    // Bottom-left corner
    ImGui::SetNextWindowPos(
        ImVec2(margin, io.DisplaySize.y - panelH - margin),
        ImGuiCond_Always);
    ImGui::SetNextWindowSize(ImVec2(panelW, panelH), ImGuiCond_Always);

    ImGuiWindowFlags flags =
        ImGuiWindowFlags_NoTitleBar  |
        ImGuiWindowFlags_NoResize    |
        ImGuiWindowFlags_NoMove      |
        ImGuiWindowFlags_NoScrollbar |
        ImGuiWindowFlags_NoScrollWithMouse;

    ImGui::PushStyleColor(ImGuiCol_WindowBg,
        ImVec4(0.039f, 0.051f, 0.059f, 0.92f));  // #0a0d0f
    ImGui::PushStyleColor(ImGuiCol_Text,
        ImVec4(0.498f, 0.702f, 0.541f, 1.0f));   // #7fb38a
    ImGui::PushStyleColor(ImGuiCol_Button,
        ImVec4(0.08f, 0.12f, 0.10f, 1.0f));
    ImGui::PushStyleColor(ImGuiCol_ButtonHovered,
        ImVec4(0.15f, 0.25f, 0.18f, 1.0f));

    ImGui::Begin("##route_panel", nullptr, flags);

    // Header
    ImGui::TextUnformatted("NAV COMPUTER");
    ImGui::Separator();

    RouteData route;
    {
        std::lock_guard<std::mutex> lock(s_mutex);
        route = s_route;
    }

    if (!route.active) {
        // Dim "no route" text
        ImGui::PushStyleColor(ImGuiCol_Text,
            ImVec4(0.30f, 0.40f, 0.32f, 1.0f));
        ImGui::TextUnformatted("NO ROUTE ACTIVE");
        ImGui::TextUnformatted("Type /route SYSTEM in the companion panel to plot.");
        ImGui::PopStyleColor();
    } else if (route.has_error) {
        ImGui::PushStyleColor(ImGuiCol_Text,
            ImVec4(0.80f, 0.30f, 0.30f, 1.0f));
        ImGui::TextUnformatted("ROUTE ERROR:");
        ImGui::TextWrapped("%s", route.error_msg.c_str());
        ImGui::PopStyleColor();
    } else {
        // Route line
        std::string routeLine = route.path_str + "  (" +
            std::to_string(route.jumps) + " jump" +
            (route.jumps != 1 ? "s" : "") + ")";
        ImGui::TextWrapped("%s", routeLine.c_str());

        // Warnings (capped at 2 for space)
        if (!route.warnings.empty()) {
            ImGui::PushStyleColor(ImGuiCol_Text,
                ImVec4(0.85f, 0.65f, 0.20f, 1.0f));  // amber
            for (size_t i = 0; i < route.warnings.size() && i < 2; ++i) {
                std::string line = "! " + route.warnings[i];
                ImGui::TextWrapped("%s", line.c_str());
            }
            ImGui::PopStyleColor();
        }

        // Highlights (capped at 1 for space)
        if (!route.highlights.empty()) {
            ImGui::PushStyleColor(ImGuiCol_Text,
                ImVec4(0.40f, 0.70f, 0.80f, 1.0f));  // cyan
            std::string line = "* " + route.highlights[0];
            ImGui::TextWrapped("%s", line.c_str());
            ImGui::PopStyleColor();
        }
    }

    // Clear button (always shown when active)
    if (route.active) {
        ImGui::Spacing();
        if (s_clearing) ImGui::BeginDisabled();
        if (ImGui::SmallButton("CLEAR ROUTE")) {
            s_clearing = true;
            std::thread([]() {
                std::string err;
                http::postEmpty("/route/clear", err);
                {
                    std::lock_guard<std::mutex> lock(s_mutex);
                    s_route = {};
                    s_clearing = false;
                }
            }).detach();
        }
        if (s_clearing) ImGui::EndDisabled();
    }

    // CRT scanline effect — subtle dark lines every 4 px
    ImDrawList* dl = ImGui::GetWindowDrawList();
    ImVec2 wMin = ImGui::GetWindowPos();
    ImVec2 wMax = ImVec2(wMin.x + panelW, wMin.y + panelH);
    for (float y = wMin.y; y < wMax.y; y += 4.0f) {
        dl->AddLine(ImVec2(wMin.x, y), ImVec2(wMax.x, y),
            IM_COL32(0, 0, 0, 35));
    }

    ImGui::End();
    ImGui::PopStyleColor(4);
}

}  // namespace route_panel
