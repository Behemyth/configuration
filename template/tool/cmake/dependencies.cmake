if(NOT DEFINED SYNODIC_BUILD_IDENTITY OR SYNODIC_BUILD_IDENTITY STREQUAL "")
    message(FATAL_ERROR "SYNODIC_BUILD_IDENTITY must be set by the selected CMake configure preset.")
endif()

if(NOT SYNODIC_BUILD_IDENTITY MATCHES "^[a-z0-9]+(-[a-z0-9]+)*$")
    message(FATAL_ERROR "Invalid SYNODIC_BUILD_IDENTITY: '${SYNODIC_BUILD_IDENTITY}'")
endif()

get_filename_component(_synodic_project_root "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
if(NOT DEFINED SYNODIC_DEPENDENCIES_ROOT OR SYNODIC_DEPENDENCIES_ROOT STREQUAL "")
    set(SYNODIC_DEPENDENCIES_ROOT "${_synodic_project_root}/build")
elseif(NOT IS_ABSOLUTE "${SYNODIC_DEPENDENCIES_ROOT}")
    message(FATAL_ERROR "SYNODIC_DEPENDENCIES_ROOT must be an absolute path.")
endif()

set(_synodic_dependency_glue
    "${SYNODIC_DEPENDENCIES_ROOT}/${SYNODIC_BUILD_IDENTITY}/deps/dependencies.cmake"
)

if(EXISTS "${_synodic_dependency_glue}")
    include("${_synodic_dependency_glue}")
else()
    message(WARNING
        "Dependencies are not prepared for '${SYNODIC_BUILD_IDENTITY}'. "
        "Run 'porr install' or make the required packages discoverable by CMake."
    )
endif()

unset(_synodic_dependency_glue)
unset(_synodic_project_root)
