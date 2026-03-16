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

struct RouteRow {
    bool        active      = false;
    std::string origin;
    std::string destination;
    std::string summary;     // "SYS-A → SYS-B   6 jumps · 142 LY · 87u"
    bool        has_error   = false;
    std::string error_msg;
    std::vector<std::string> warnings;
};

struct PanelState {
    RouteRow primary;
    RouteRow alt;
    bool     has_alt        = false;
    bool     primary_active = true;  // which variant is "current_route"
};

static PanelState           s_state;
static std::mutex           s_mutex;
static std::atomic<bool>    s_running    { false };
static std::thread          s_poller;
static std::atomic<bool>    s_activating { false };
static std::atomic<bool>    s_clearing   { false };

static RouteRow _parseRoute(const nlohmann::json& route) {
    RouteRow r;
    if (route.is_null()) return r;
    r.active = true;
    if (route.contains("error") && !route["error"].is_null()) {
        r.has_error = true;
        r.error_msg = route["error"].get<std::string>();
        return r;
    }
    auto path  = route.value("path", nlohmann::json::array());
    int  jumps = route.value("jumps", 0);
    float total_ly  = route.value("total_ly", 0.0f);
    float fuel_used = route.value("fuel_used", 0.0f);

    r.origin      = path.empty() ? "" : path.front().get<std::string>();
    r.destination = path.empty() ? "" : path.back().get<std::string>();

    // Build summary line: "SYS-A → SYS-B   6 jumps · 142 LY · 87u"
    auto toUpper = [](std::string s) {
        for (auto& c : s) c = (char)toupper((unsigned char)c);
        return s;
    };
    r.summary = toUpper(r.origin) + " \xe2\x86\x92 " + toUpper(r.destination)
              + "   " + std::to_string(jumps)
              + " jump" + (jumps != 1 ? "s" : "");
    if (total_ly > 0.0f) {
        char buf[64];
        snprintf(buf, sizeof(buf), " \xc2\xb7 %.0f LY", total_ly);
        r.summary += buf;
    }
    if (fuel_used > 0.0f) {
        char buf[32];
        snprintf(buf, sizeof(buf), " \xc2\xb7 %.0fu", fuel_used);
        r.summary += buf;
    }
    for (auto& w : route.value("warnings", nlohmann::json::array()))
        r.warnings.push_back(w.get<std::string>());
    return r;
}

static void _poll() {
    std::string body, err;
    if (!http::getJson("/current-route", body, err))
        return;
    try {
        auto j = nlohmann::json::parse(body);
        std::lock_guard<std::mutex> lock(s_mutex);
        auto& route = j["route"];
        nlohmann::json alt_json = j.contains("alternative") ? j["alternative"] : nlohmann::json();

        s_state.primary     = _parseRoute(route);
        s_state.has_alt     = !alt_json.is_null();
        s_state.alt         = _parseRoute(alt_json);
        s_state.primary_active = true;  // server always returns current_route as primary
    } catch (...) {}
}

static void _pollerThread() {
    while (s_running.load()) {
        _poll();
        for (int i = 0; i < 50 && s_running.load(); ++i)
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

void init() { s_running = true; s_poller = std::thread(_pollerThread); }
void shutdown() { s_running = false; if (s_poller.joinable()) s_poller.join(); }

void draw() {
    ImGuiIO& io = ImGui::GetIO();
    const float panelW = 440.0f;
    const float panelH = 260.0f;
    const float margin = 16.0f;

    ImGui::SetNextWindowPos(
        ImVec2(margin, io.DisplaySize.y - panelH - margin), ImGuiCond_Always);
    ImGui::SetNextWindowSize(ImVec2(panelW, panelH), ImGuiCond_Always);

    ImGuiWindowFlags flags =
        ImGuiWindowFlags_NoTitleBar  | ImGuiWindowFlags_NoResize |
        ImGuiWindowFlags_NoMove      | ImGuiWindowFlags_NoScrollbar |
        ImGuiWindowFlags_NoScrollWithMouse;

    ImGui::PushStyleColor(ImGuiCol_WindowBg,   ImVec4(0.039f, 0.051f, 0.059f, 0.92f));
    ImGui::PushStyleColor(ImGuiCol_Text,       ImVec4(0.498f, 0.702f, 0.541f, 1.0f));
    ImGui::PushStyleColor(ImGuiCol_Button,     ImVec4(0.08f, 0.12f, 0.10f, 1.0f));
    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.15f, 0.25f, 0.18f, 1.0f));

    ImGui::Begin("##route_panel", nullptr, flags);
    ImGui::TextUnformatted("NAV COMPUTER");
    ImGui::Separator();

    PanelState state;
    { std::lock_guard<std::mutex> lock(s_mutex); state = s_state; }

    if (!state.primary.active) {
        ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.30f, 0.40f, 0.32f, 1.0f));
        ImGui::TextUnformatted("NO ROUTE ACTIVE");
        ImGui::TextUnformatted("Type /route SYSTEM in the companion panel.");
        ImGui::PopStyleColor();
    } else {
        // Render a route row: bright green if isActive, dimmed otherwise
        auto renderRow = [&](const RouteRow& row, bool isActive, const char* variant) {
            ImVec4 textColor = isActive
                ? ImVec4(0.498f, 0.702f, 0.541f, 1.0f)  // bright green
                : ImVec4(0.30f,  0.40f,  0.32f,  1.0f);  // dimmed
            ImGui::PushStyleColor(ImGuiCol_Text, textColor);
            if (row.has_error) {
                ImGui::TextUnformatted("ROUTE ERROR:");
                ImGui::TextWrapped("%s", row.error_msg.c_str());
            } else {
                ImGui::TextWrapped("%s", row.summary.c_str());
                for (size_t i = 0; i < row.warnings.size() && i < 2; ++i) {
                    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.85f, 0.65f, 0.20f, 1.0f));
                    ImGui::TextWrapped("! %s", row.warnings[i].c_str());
                    ImGui::PopStyleColor();
                }
            }
            ImGui::PopStyleColor();
            ImGui::SameLine(panelW - 68.0f);
            if (!isActive) {
                if (s_activating) ImGui::BeginDisabled();
                std::string btnLabel = std::string("[USE]##") + variant;
                if (ImGui::SmallButton(btnLabel.c_str())) {
                    s_activating = true;
                    std::string v = variant;
                    std::thread([v]() {
                        std::string body, err;
                        std::string payload = "{\"variant\":\"" + v + "\"}";
                        http::postJson("/route/activate", payload, body, err);
                        s_activating = false;
                    }).detach();
                }
                if (s_activating) ImGui::EndDisabled();
            }
        };

        renderRow(state.primary, state.primary_active, "primary");
        if (state.has_alt) {
            ImGui::Separator();
            renderRow(state.alt, !state.primary_active, "alternative");
        }
    }

    ImGui::Separator();
    if (state.primary.active) {
        if (s_clearing) ImGui::BeginDisabled();
        if (ImGui::SmallButton("CLEAR ROUTE")) {
            s_clearing = true;
            std::thread([]() {
                std::string err;
                http::postEmpty("/route/clear", err);
                { std::lock_guard<std::mutex> lock(s_mutex);
                  s_state = {}; s_clearing = false; }
            }).detach();
        }
        if (s_clearing) ImGui::EndDisabled();
    }

    // CRT scanlines
    ImDrawList* dl = ImGui::GetWindowDrawList();
    ImVec2 wMin = ImGui::GetWindowPos();
    ImVec2 wMax = ImVec2(wMin.x + panelW, wMin.y + panelH);
    for (float y = wMin.y; y < wMax.y; y += 4.0f)
        dl->AddLine(ImVec2(wMin.x, y), ImVec2(wMax.x, y), IM_COL32(0, 0, 0, 35));

    ImGui::End();
    ImGui::PopStyleColor(4);
}

}  // namespace route_panel
