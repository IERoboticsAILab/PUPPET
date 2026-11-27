cmake_minimum_required(VERSION 3.16)
project(natnet_bridge LANGUAGES CXX)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(tf2_ros REQUIRED)

# OptiTrack NatNet SDK 4.0 for Ubuntu (same download as ros_ws/src/natnet_ros_cpp/install_sdk.sh).
# Fetched at configure time into the build directory; set NATNET_SDK_DIR to use a local copy.
set(NATNET_SDK_URL "https://s3.amazonaws.com/naturalpoint/software/NatNetSDKLinux/ubuntu/NatNet_SDK_4.0_ubuntu.tar")
if(NOT NATNET_SDK_DIR)
  set(NATNET_SDK_DIR "${CMAKE_BINARY_DIR}/NatNetSDK")
  if(NOT EXISTS "${NATNET_SDK_DIR}/lib/libNatNet.so")
    message(STATUS "Downloading NatNet SDK from ${NATNET_SDK_URL}")
    file(DOWNLOAD "${NATNET_SDK_URL}" "${CMAKE_BINARY_DIR}/NatNetSDK.tar" STATUS dl)
    list(GET dl 0 dl_code)
    if(NOT dl_code EQUAL 0)
      message(FATAL_ERROR "NatNet SDK download failed (${dl}). Download it by hand and pass -DNATNET_SDK_DIR=<dir with include/ and lib/>.")
    endif()
    file(MAKE_DIRECTORY "${NATNET_SDK_DIR}")
    execute_process(COMMAND ${CMAKE_COMMAND} -E tar xf "${CMAKE_BINARY_DIR}/NatNetSDK.tar" WORKING_DIRECTORY "${NATNET_SDK_DIR}")
  endif()
endif()
if(NOT EXISTS "${NATNET_SDK_DIR}/lib/libNatNet.so")
  message(FATAL_ERROR "libNatNet.so not found under ${NATNET_SDK_DIR}/lib")
endif()

add_executable(natnet_bridge src/natnet_bridge.cpp)
target_include_directories(natnet_bridge PRIVATE "${NATNET_SDK_DIR}/include")
target_link_libraries(natnet_bridge "${NATNET_SDK_DIR}/lib/libNatNet.so")
ament_target_dependencies(natnet_bridge rclcpp geometry_msgs tf2_ros)
# install/lib/natnet_bridge/natnet_bridge finds install/lib/libNatNet.so
set_target_properties(natnet_bridge PROPERTIES INSTALL_RPATH "$ORIGIN/..")

install(TARGETS natnet_bridge DESTINATION lib/${PROJECT_NAME})
install(FILES "${NATNET_SDK_DIR}/lib/libNatNet.so" DESTINATION lib)
ament_package()
