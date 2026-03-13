add_executable(injector main.cpp)
target_compile_definitions(injector PRIVATE UNICODE _UNICODE)
target_link_libraries(injector PRIVATE)
set_target_properties(injector PROPERTIES
    WIN32_EXECUTABLE FALSE
)
