add_library(overlay_core SHARED
    dllmain.cpp
    hook.cpp
    imgui_init.cpp
    input.cpp
    frame.cpp
)
set_target_properties(overlay_core PROPERTIES OUTPUT_NAME "overlay")
target_compile_definitions(overlay_core PRIVATE UNICODE _UNICODE)
target_link_libraries(overlay_core PRIVATE
    imgui_dx12
    overlay_ui
    shared
    minhook
    d3d12
    dxgi
    d3dcompiler
)
