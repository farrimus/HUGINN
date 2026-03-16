add_library(overlay_ui STATIC
    render.cpp
    companion_panel.cpp
    http_client.cpp
    route_panel.cpp
    ship_profile_panel.cpp
)
target_compile_definitions(overlay_ui PRIVATE UNICODE _UNICODE)
target_link_libraries(overlay_ui PUBLIC imgui_dx12 winhttp nlohmann_json::nlohmann_json)
