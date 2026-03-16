#include "ship_profile_panel.h"
#include "http_client.h"
#include <imgui.h>
#include <string>
#include <vector>
#include <thread>
#include <atomic>
#include <cmath>
#include <nlohmann/json.hpp>

namespace ship_profile_panel {

// Panel visibility toggled by F7
bool g_visible = false;

// Ship + fuel constant tables (mirrors server SHIPS/FUEL_QUALITY)
struct ShipEntry { const char* name; float mass; float specific_heat; bool advanced; int max_fuel; };
static const ShipEntry SHIPS[] = {
    {"Carom",   7200000.f,      8.5f, false, 3000},
    {"Stride",  7900000.f,      8.0f, false, 3200},
    {"Reflex",  9750000.f,      3.0f, false, 1750},
    {"Recurve", 10200000.f,     1.0f, false,  970},
    {"Reiver",  10400000.f,     1.0f, false, 1416},
    {"Lai",     18929160.f,     2.5f, true,  2400},
    {"USV",     30266600.f,     1.8f, true,  2420},
    {"Lorha",   42691330.f,     2.5f, true,  2508},
    {"MCF",     52313760.f,     2.5f, true,  6548},
    {"Tades",   74655480.f,     2.5f, true,  5972},
    {"HAF",     81883000.f,     2.5f, true,  4184},
    {"Maul",    548435920.f,    2.5f, true, 24160},
    {"Chumaq",  1487392000.f,   3.0f, true, 270585},
};
static const int SHIP_COUNT = (int)(sizeof(SHIPS)/sizeof(SHIPS[0]));

struct FuelEntry { const char* code; float quality; bool advanced; };
static const FuelEntry FUELS[] = {
    {"D1",     0.10f, false},
    {"D2",     0.15f, false},
    {"SOF-40", 0.40f, true},
    {"EU-40",  0.40f, true},
    {"SOF-80", 0.80f, true},
    {"EU-90",  0.90f, true},
};
static const int FUEL_COUNT = (int)(sizeof(FUELS)/sizeof(FUELS[0]));

// UI state
static int   s_ship_idx    = 0;
static int   s_fuel_idx    = 0;
static int   s_fuel_units  = 500;
static int   s_adaptive    = 0;
static int   s_extra_cargo = 0;

// Polled from /current-route — written by poller thread, read by render thread
static std::atomic<float> s_cur_temp{-1.0f};  // -1 = unknown

// Save feedback
static std::atomic<int> s_save_state{0};  // 0=idle 1=saving 2=saved 3=error

static float _computeRange(int ship_idx, int adaptive, int extra_cargo, float temp) {
    if (ship_idx < 0 || ship_idx >= SHIP_COUNT) return 0.0f;
    const auto& s = SHIPS[ship_idx];
    if (temp >= 90.0f) return 0.0f;
    float c_eff   = s.specific_heat * (1.0f + adaptive * 0.02f);
    float cur_m   = s.mass + extra_cargo;
    return ((150.0f - temp) * c_eff * s.mass) / (3.0f * cur_m);
}

static float _computeBudget(int ship_idx, int fuel_idx, int fuel_units, int extra_cargo) {
    if (ship_idx < 0 || ship_idx >= SHIP_COUNT) return 0.0f;
    if (fuel_idx < 0 || fuel_idx >= FUEL_COUNT) return 0.0f;
    float cur_m   = SHIPS[ship_idx].mass + extra_cargo;
    float quality = FUELS[fuel_idx].quality;
    return (fuel_units * quality) / (1e-7f * cur_m);
}

static void _fetchTempFromCurrentRoute() {
    std::string body, err;
    if (!http::getJson("/current-route", body, err)) return;
    try {
        auto j = nlohmann::json::parse(body);
        if (j.contains("current_system_temp") && !j["current_system_temp"].is_null())
            s_cur_temp.store(j["current_system_temp"].get<float>());
        else
            s_cur_temp.store(-1.0f);
    } catch (...) {}
}

// Background temp poller
static std::atomic<bool> s_poll_running{false};
static std::thread s_poller;

static void _pollerThread() {
    while (s_poll_running.load()) {
        _fetchTempFromCurrentRoute();
        for (int i = 0; i < 50 && s_poll_running.load(); ++i)
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

void init() {
    s_poll_running = true;
    s_poller = std::thread(_pollerThread);
}

void shutdown() {
    s_poll_running = false;
    if (s_poller.joinable()) s_poller.join();
}

void draw() {
    if (!g_visible) return;

    const float panelW = 440.0f;
    const float panelH = 280.0f;
    const float margin = 16.0f;

    ImGui::SetNextWindowPos(ImVec2(margin, margin), ImGuiCond_Always);
    ImGui::SetNextWindowSize(ImVec2(panelW, panelH), ImGuiCond_Always);

    ImGuiWindowFlags flags =
        ImGuiWindowFlags_NoTitleBar  | ImGuiWindowFlags_NoResize |
        ImGuiWindowFlags_NoMove      | ImGuiWindowFlags_NoScrollbar |
        ImGuiWindowFlags_NoScrollWithMouse;

    ImGui::PushStyleColor(ImGuiCol_WindowBg,      ImVec4(0.039f, 0.051f, 0.059f, 0.92f));
    ImGui::PushStyleColor(ImGuiCol_Text,          ImVec4(0.498f, 0.702f, 0.541f, 1.0f));
    ImGui::PushStyleColor(ImGuiCol_Button,        ImVec4(0.08f, 0.12f, 0.10f, 1.0f));
    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.15f, 0.25f, 0.18f, 1.0f));
    ImGui::PushStyleColor(ImGuiCol_FrameBg,       ImVec4(0.08f, 0.12f, 0.10f, 1.0f));

    ImGui::Begin("##ship_profile_panel", nullptr, flags);
    ImGui::TextUnformatted("SHIP PROFILE                            [F7]");
    ImGui::Separator();

    // Determine whether current ship is advanced or basic
    bool isAdvanced = (s_ship_idx >= 0 && s_ship_idx < SHIP_COUNT)
                    ? SHIPS[s_ship_idx].advanced : false;

    // Ship type dropdown
    ImGui::Text("Ship type:");
    ImGui::SameLine(120.0f);
    ImGui::SetNextItemWidth(200.0f);
    if (ImGui::BeginCombo("##ship", s_ship_idx >= 0 ? SHIPS[s_ship_idx].name : "---")) {
        for (int i = 0; i < SHIP_COUNT; ++i) {
            bool sel = (i == s_ship_idx);
            if (ImGui::Selectable(SHIPS[i].name, sel)) {
                bool wasAdv = isAdvanced;
                s_ship_idx  = i;
                isAdvanced  = SHIPS[i].advanced;
                // Reset fuel type to category default if category changed
                if (wasAdv != isAdvanced) {
                    s_fuel_idx  = isAdvanced ? 2 : 0;  // SOF-40 or D1
                }
                // Clamp fuel_units to new max
                int max = SHIPS[s_ship_idx].max_fuel;
                if (s_fuel_units > max) s_fuel_units = max;
            }
            if (sel) ImGui::SetItemDefaultFocus();
        }
        ImGui::EndCombo();
    }

    // Fuel type dropdown (filtered by category)
    ImGui::Text("Fuel type:");
    ImGui::SameLine(120.0f);
    ImGui::SetNextItemWidth(120.0f);
    const char* curFuel = (s_fuel_idx >= 0 && s_fuel_idx < FUEL_COUNT)
                        ? FUELS[s_fuel_idx].code : "---";
    if (ImGui::BeginCombo("##fuel", curFuel)) {
        for (int i = 0; i < FUEL_COUNT; ++i) {
            if (FUELS[i].advanced != isAdvanced) continue;
            bool sel = (i == s_fuel_idx);
            if (ImGui::Selectable(FUELS[i].code, sel)) s_fuel_idx = i;
            if (sel) ImGui::SetItemDefaultFocus();
        }
        ImGui::EndCombo();
    }

    // Fuel units
    int maxFuel = (s_ship_idx >= 0 && s_ship_idx < SHIP_COUNT)
                ? SHIPS[s_ship_idx].max_fuel : 99999;
    ImGui::Text("Fuel units:");
    ImGui::SameLine(120.0f);
    ImGui::SetNextItemWidth(100.0f);
    ImGui::InputInt("##fu", &s_fuel_units, 10, 100);
    if (s_fuel_units < 0) s_fuel_units = 0;
    if (s_fuel_units > maxFuel) s_fuel_units = maxFuel;

    // Adaptive level
    ImGui::Text("Adaptive:");
    ImGui::SameLine(120.0f);
    ImGui::SetNextItemWidth(80.0f);
    ImGui::InputInt("##al", &s_adaptive, 1, 1);
    if (s_adaptive < 0) s_adaptive = 0;
    if (s_adaptive > 10) s_adaptive = 10;

    // Extra cargo
    ImGui::Text("Extra cargo:");
    ImGui::SameLine(120.0f);
    ImGui::SetNextItemWidth(120.0f);
    ImGui::InputInt("##xc", &s_extra_cargo, 1000, 10000);
    if (s_extra_cargo < 0) s_extra_cargo = 0;

    ImGui::Separator();

    // Computed display
    float cur_temp_val = s_cur_temp.load();
    float temp    = cur_temp_val >= 0.0f ? cur_temp_val : 0.0f;
    bool  hasTemp = cur_temp_val >= 0.0f;
    float range   = _computeRange(s_ship_idx, s_adaptive, s_extra_cargo, temp);
    float budget  = _computeBudget(s_ship_idx, s_fuel_idx, s_fuel_units, s_extra_cargo);

    if (hasTemp) {
        ImGui::Text("JUMP RANGE:  %.1f LY  (at %.1f deg)", range, temp);
    } else {
        ImGui::Text("JUMP RANGE:  ---  (system unknown)");
    }
    ImGui::Text("FUEL BUDGET: %.1f LY", budget);

    ImGui::Spacing();

    // SAVE button
    int saveState = s_save_state.load();
    if (saveState == 1) ImGui::BeginDisabled();
    if (ImGui::Button("SAVE##profile")) {
        s_save_state = 1;
        // Build JSON payload
        nlohmann::json payload;
        if (s_ship_idx >= 0 && s_ship_idx < SHIP_COUNT)
            payload["ship_type"]    = SHIPS[s_ship_idx].name;
        if (s_fuel_idx >= 0 && s_fuel_idx < FUEL_COUNT)
            payload["fuel_type"]    = FUELS[s_fuel_idx].code;
        payload["fuel_quantity"]    = s_fuel_units;
        payload["adaptive_level"]   = s_adaptive;
        payload["extra_cargo_kg"]   = s_extra_cargo;
        std::string body_str = payload.dump();

        std::thread([body_str]() {
            std::string resp, err;
            bool ok = http::postJson("/ship-profile", body_str, resp, err);
            s_save_state = ok ? 2 : 3;
            // Reset after 2 seconds
            std::this_thread::sleep_for(std::chrono::seconds(2));
            s_save_state = 0;
        }).detach();
    }
    if (saveState == 1) ImGui::EndDisabled();
    ImGui::SameLine();
    if (saveState == 2) {
        ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.3f, 0.8f, 0.3f, 1.0f));
        ImGui::TextUnformatted("SAVED");
        ImGui::PopStyleColor();
    } else if (saveState == 3) {
        ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.8f, 0.3f, 0.3f, 1.0f));
        ImGui::TextUnformatted("ERROR");
        ImGui::PopStyleColor();
    }

    // CRT scanlines
    ImDrawList* dl = ImGui::GetWindowDrawList();
    ImVec2 wMin = ImGui::GetWindowPos();
    ImVec2 wMax = ImVec2(wMin.x + panelW, wMin.y + panelH);
    for (float y = wMin.y; y < wMax.y; y += 4.0f)
        dl->AddLine(ImVec2(wMin.x, y), ImVec2(wMax.x, y), IM_COL32(0, 0, 0, 35));

    ImGui::End();
    ImGui::PopStyleColor(5);
}

}  // namespace ship_profile_panel
