# [KiCad-IOS port] Minimal iOS cross-compile toolchain for dependency
# builds (GPLv3-or-later, matching upstream KiCad). Modelled on the
# FEBio iOS port's proven toolchain file; the macOS CI runner supplies
# the SDK, we only pin the target.
set(CMAKE_SYSTEM_NAME iOS)
set(CMAKE_SYSTEM_PROCESSOR arm64)
set(CMAKE_OSX_ARCHITECTURES arm64)
set(CMAKE_OSX_DEPLOYMENT_TARGET 17.0)

# try_compile must not attempt to link/sign an executable.
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
