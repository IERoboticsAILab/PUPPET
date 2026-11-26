cmake_minimum_required(VERSION 3.16)
project(tiago_telepresence_controllers LANGUAGES C CXX)

# ROS 2 (ament) port of ros_ws/src/tiago_telepresence_controllers. Same package name on purpose:
# Unity sends the type name tiago_telepresence_controllers/ArmMotion on both ROS 1 and ROS 2.

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
add_compile_options(-Wall -Wextra)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(controller_interface REQUIRED)
find_package(hardware_interface REQUIRED)
find_package(pluginlib REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(kdl_parser REQUIRED)
find_package(urdf REQUIRED)
find_package(orocos_kdl REQUIRED)
find_package(Eigen3 REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  msg/JointPositions.msg
  srv/ArmMotion.srv
  DEPENDENCIES std_msgs
)
rosidl_get_typesupport_target(cpp_typesupport_target ${PROJECT_NAME} rosidl_typesupport_cpp)

add_library(${PROJECT_NAME}_controllers SHARED
  src/command_buffer.cpp
  src/controller_base.cpp
  src/arm_tp_controller.cpp
  src/head_torso_gripper_tp_controllers.cpp
)
target_include_directories(${PROJECT_NAME}_controllers PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include/${PROJECT_NAME}>
  ${EIGEN3_INCLUDE_DIR}
)
target_link_libraries(${PROJECT_NAME}_controllers "${cpp_typesupport_target}" ${orocos_kdl_LIBRARIES})
ament_target_dependencies(${PROJECT_NAME}_controllers
  builtin_interfaces std_msgs geometry_msgs controller_interface hardware_interface pluginlib
  rclcpp rclcpp_lifecycle kdl_parser urdf orocos_kdl
)
pluginlib_export_plugin_description_file(controller_interface tiago_telepresence_controllers_plugins.xml)

install(TARGETS ${PROJECT_NAME}_controllers
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)
install(DIRECTORY include/ DESTINATION include/${PROJECT_NAME})
install(DIRECTORY config launch DESTINATION share/${PROJECT_NAME})
install(PROGRAMS scripts/arm_motion.py scripts/tp_controller_switcher.py scripts/puppet_endpoint.py scripts/play_motion.py DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_command_buffer test/test_command_buffer.cpp)
  target_link_libraries(test_command_buffer ${PROJECT_NAME}_controllers)
endif()

ament_export_dependencies(rosidl_default_runtime)
ament_package()
