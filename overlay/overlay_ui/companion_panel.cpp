#include "companion_panel.h"
#include "http_client.h"
#include <imgui.h>
#include <string>
#include <vector>
#include <mutex>
#include <thread>
#include <nlohmann/json.hpp>

namespace companion_panel {

struct Message {
    bool        isUser;
    std::string text;
    bool        streaming;
};

static std::vector<Message> s_messages;
static char                 s_inputBuf[512] = {};
static bool                 s_sending       = false;
static std::mutex           s_mutex;
static bool                 s_scrollToBottom = false;
static std::string          s_statusLine;

static void send(const std::string& text) {
    {
        std::lock_guard<std::mutex> lock(s_mutex);
        s_messages.push_back({ true,  text, false });
        s_messages.push_back({ false, "",   true  });
        s_sending    = true;
        s_statusLine = "connecting...";
    }

    std::thread([text]() {
        // Build history (capped at last 40 entries, excluding the new streaming message)
        nlohmann::json history = nlohmann::json::array();
        {
            std::lock_guard<std::mutex> lock(s_mutex);
            // s_messages tail: [..., user_msg, streaming_assistant]
            // History excludes the two messages we just pushed
            size_t histEnd = s_messages.size() >= 2 ? s_messages.size() - 2 : 0;
            size_t histStart = histEnd > 40 ? histEnd - 40 : 0;
            for (size_t i = histStart; i < histEnd; ++i) {
                history.push_back({
                    {"role",    s_messages[i].isUser ? "user" : "assistant"},
                    {"content", s_messages[i].text}
                });
            }
        }

        nlohmann::json body = {
            {"message", text},
            {"history", history}
        };
        std::string jsonBody = body.dump();

        auto onChunk = [](const std::string& chunk) {
            std::lock_guard<std::mutex> lock(s_mutex);
            if (!s_messages.empty())
                s_messages.back().text += chunk;
            s_scrollToBottom = true;
        };

        auto onDone = []() {
            std::lock_guard<std::mutex> lock(s_mutex);
            if (!s_messages.empty())
                s_messages.back().streaming = false;
            s_sending    = false;
            s_statusLine = "";
        };

        std::string error;
        bool ok = http::postChat(jsonBody, onChunk, onDone, error);
        if (!ok) {
            std::lock_guard<std::mutex> lock(s_mutex);
            if (!s_messages.empty()) {
                s_messages.back().text      = "[error: " + error + "]";
                s_messages.back().streaming = false;
            }
            s_sending    = false;
            s_statusLine = "";
        }
    }).detach();
}

void draw() {
    ImGuiIO& io = ImGui::GetIO();

    // Fixed position: right side, full height with small margin
    const float panelW = 400.0f;
    const float panelH = 600.0f;
    const float margin = 16.0f;
    ImGui::SetNextWindowPos(
        ImVec2(io.DisplaySize.x - panelW - margin,
               (io.DisplaySize.y - panelH) * 0.5f),
        ImGuiCond_Always);
    ImGui::SetNextWindowSize(ImVec2(panelW, panelH), ImGuiCond_Always);

    ImGuiWindowFlags flags =
        ImGuiWindowFlags_NoTitleBar    |
        ImGuiWindowFlags_NoResize      |
        ImGuiWindowFlags_NoMove        |
        ImGuiWindowFlags_NoScrollbar   |
        ImGuiWindowFlags_NoScrollWithMouse;

    ImGui::PushStyleColor(ImGuiCol_WindowBg,
        ImVec4(0.039f, 0.051f, 0.059f, 0.95f));  // #0a0d0f
    ImGui::PushStyleColor(ImGuiCol_Text,
        ImVec4(0.498f, 0.702f, 0.541f, 1.0f));   // #7fb38a

    ImGui::Begin("##companion", nullptr, flags);

    // Header row
    ImGui::TextUnformatted("SHIP SYSTEMS // ONLINE");
    ImGui::SameLine(panelW - 36.0f);
    if (ImGui::SmallButton(" - ")) {
        // Close: caller (render.cpp) controls ui::visible;
        // signal via a simple flag checked in render.cpp
        // For now, toggle is via F8 — this button is visual only.
    }
    ImGui::Separator();

    // Message area
    const float inputRowH  = ImGui::GetFrameHeightWithSpacing() * 2.0f + 8.0f;
    const float statusRowH = ImGui::GetTextLineHeightWithSpacing();
    float msgAreaH = panelH
        - ImGui::GetCursorPosY()
        - inputRowH
        - statusRowH
        - 8.0f;
    if (msgAreaH < 32.0f) msgAreaH = 32.0f;

    ImGui::BeginChild("##messages", ImVec2(0, msgAreaH), false,
        ImGuiWindowFlags_NoScrollbar);

    {
        std::lock_guard<std::mutex> lock(s_mutex);
        for (const auto& msg : s_messages) {
            if (msg.isUser) {
                // Right-align pilot messages in lighter green
                ImGui::PushStyleColor(ImGuiCol_Text,
                    ImVec4(0.702f, 0.871f, 0.741f, 1.0f));  // lighter green
                std::string line = "PILOT: " + msg.text;
                float textW = ImGui::CalcTextSize(line.c_str()).x;
                ImGui::SetCursorPosX(panelW - textW - 16.0f);
                ImGui::TextUnformatted(line.c_str());
                ImGui::PopStyleColor();
            } else {
                std::string line = "> " + msg.text;
                if (msg.streaming) line += "\xe2\x96\x88";  // UTF-8 block cursor
                ImGui::TextWrapped("%s", line.c_str());
            }
        }
    }

    if (s_scrollToBottom) {
        ImGui::SetScrollHereY(1.0f);
        std::lock_guard<std::mutex> lock(s_mutex);
        s_scrollToBottom = false;
    }

    ImGui::EndChild();

    // Status bar
    if (!s_statusLine.empty()) {
        ImGui::PushStyleColor(ImGuiCol_Text,
            ImVec4(0.4f, 0.4f, 0.4f, 1.0f));
        ImGui::TextUnformatted(s_statusLine.c_str());
        ImGui::PopStyleColor();
    } else {
        ImGui::Spacing();
    }

    // Input row
    bool enterPressed = false;
    ImGui::PushItemWidth(panelW - 80.0f);
    if (ImGui::InputText("##input", s_inputBuf, sizeof(s_inputBuf),
            ImGuiInputTextFlags_EnterReturnsTrue)) {
        enterPressed = true;
    }
    ImGui::PopItemWidth();
    ImGui::SameLine();

    if (s_sending) ImGui::BeginDisabled();
    bool sendClicked = ImGui::Button("SEND");
    if (s_sending) ImGui::EndDisabled();

    if ((enterPressed || sendClicked) && !s_sending && s_inputBuf[0] != '\0') {
        send(std::string(s_inputBuf));
        s_inputBuf[0] = '\0';
        ImGui::SetKeyboardFocusHere(-1);
    }

    ImGui::End();
    ImGui::PopStyleColor(2);
}

}  // namespace companion_panel
