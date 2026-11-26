#include "tiago_telepresence_controllers/controller_base.hpp"

#include <algorithm>
#include <memory>

#include <hardware_interface/types/hardware_interface_type_values.hpp>
#include <urdf/model.h>

namespace tiago_telepresence_controllers
{

CallbackReturn ControllerBase::on_init()
{
  try {
    auto_declare<std::vector<std::string>>("joint_names", std::vector<std::string>());
    auto_declare<double>("state_publish_throttle", 0.0);
    declareParameters();
  } catch (const std::exception & e) {
    RCLCPP_ERROR(logger(), "[%s] Could not declare parameters: %s", name.c_str(), e.what());
    return CallbackReturn::ERROR;
  }
  return CallbackReturn::SUCCESS;
}

controller_interface::InterfaceConfiguration ControllerBase::command_interface_configuration() const
{
  controller_interface::InterfaceConfiguration config;
  config.type = controller_interface::interface_configuration_type::INDIVIDUAL;
  for (const auto & joint : jointNames) {
    config.names.push_back(joint + "/" + hardware_interface::HW_IF_POSITION);
  }
  return config;
}

controller_interface::InterfaceConfiguration ControllerBase::state_interface_configuration() const
{
  return command_interface_configuration();
}

CallbackReturn ControllerBase::on_configure(const rclcpp_lifecycle::State &)
{
  RCLCPP_INFO(logger(), "Configuring %s controller", name.c_str());

  jointNames = get_node()->get_parameter("joint_names").as_string_array();
  if (jointNames.empty()) {
    RCLCPP_ERROR(logger(), "[%s] Parameter joint_names is empty (is telepresence_controllers.yaml loaded?)", name.c_str());
    return CallbackReturn::ERROR;
  }

  const std::string & description = get_robot_description();
  if (description.empty()) {
    RCLCPP_ERROR(logger(), "[%s] controller_manager has no robot_description yet", name.c_str());
    return CallbackReturn::ERROR;
  }

  urdf::Model model;
  if (!model.initString(description)) {
    RCLCPP_ERROR(logger(), "[%s] Failed to parse URDF", name.c_str());
    return CallbackReturn::ERROR;
  }

  jointLimits.clear();
  for (const auto & jointName : jointNames) {
    const auto joint = model.getJoint(jointName);
    if (!joint) {
      RCLCPP_ERROR(logger(), "[%s] Joint %s is not in the URDF", name.c_str(), jointName.c_str());
      return CallbackReturn::ERROR;
    }
    if (joint->limits && joint->type != urdf::Joint::CONTINUOUS) {
      jointLimits.emplace_back(joint->limits->lower, joint->limits->upper);
    } else {
      jointLimits.emplace_back(-std::numeric_limits<double>::infinity(), std::numeric_limits<double>::infinity());
    }
  }

  statePublishThrottle = get_node()->get_parameter("state_publish_throttle").as_double();
  if (statePublishThrottle > 0.0) {
    pub = get_node()->create_publisher<JointPositions>("~/state", rclcpp::QoS(1));
  }

  registerSubscriber();

  return additionalSetup(description) ? CallbackReturn::SUCCESS : CallbackReturn::ERROR;
}

CallbackReturn ControllerBase::on_activate(const rclcpp_lifecycle::State &)
{
  if (command_interfaces_.size() != jointNames.size() || state_interfaces_.size() != jointNames.size()) {
    RCLCPP_ERROR(logger(), "[%s] Expected %zu command and state interfaces, got %zu and %zu", name.c_str(),
                 jointNames.size(), command_interfaces_.size(), state_interfaces_.size());
    return CallbackReturn::ERROR;
  }

  std::string out;
  for (std::size_t i = 0; i < jointNames.size(); i++) {
    const auto expected = jointNames[i] + "/" + hardware_interface::HW_IF_POSITION;
    if (command_interfaces_[i].get_name() != expected || state_interfaces_[i].get_name() != expected) {
      RCLCPP_ERROR(logger(), "[%s] Interface %zu is %s, expected %s", name.c_str(), i,
                   command_interfaces_[i].get_name().c_str(), expected.c_str());
      return CallbackReturn::ERROR;
    }
    // Hold the current position, so taking over from PAL's controller never jumps.
    const double q = readValue(state_interfaces_[i]);
    if (std::isfinite(q)) {
      (void)command_interfaces_[i].set_value(q);
    }
    out += " " + std::to_string(q);
  }

  RCLCPP_INFO(logger(), "Activated %s controller, joints:%s", name.c_str(), out.c_str());
  isActive = false;
  stampNs = 0;
  return CallbackReturn::SUCCESS;
}

CallbackReturn ControllerBase::on_deactivate(const rclcpp_lifecycle::State &)
{
  if (isActive) {
    isActive = false;
    onDisabling();
  }
  return CallbackReturn::SUCCESS;
}

void ControllerBase::updateStamp()
{
  stampNs = get_node()->now().nanoseconds();
}

controller_interface::return_type ControllerBase::update(const rclcpp::Time &, const rclcpp::Duration & period)
{
  // Compare nanoseconds from the same (node) clock: rclcpp::Time throws on mixed clock types.
  const int64_t nowNs = get_node()->now().nanoseconds();

  JointPositions msg;
  msg.positions.reserve(state_interfaces_.size());
  for (const auto & itf : state_interfaces_) {
    msg.positions.push_back(readValue(itf));
  }

  if (std::any_of(msg.positions.cbegin(), msg.positions.cend(), [](double q) {return !std::isfinite(q);})) {
    RCLCPP_WARN_THROTTLE(logger(), clock(), UPDATE_LOG_THROTTLE_MS, "[%s] Joint state not available, holding", name.c_str());
    return controller_interface::return_type::OK;
  }

  const int64_t last = stampNs.load();
  if (last == 0 || (nowNs - last) * 1e-9 > INPUT_TIMEOUT) {
    if (isActive) {
      isActive = false;
      onDisabling();
    }
  } else {
    if (!isActive) {
      isActive = true;
      onStarting(msg.positions);
    }

    const auto desired = getDesiredJointValues(msg.positions, period.seconds());

    for (std::size_t i = 0; i < command_interfaces_.size(); i++) {
      const auto & limits = jointLimits[i];
      auto cmd = desired[i];

      if (cmd < limits.first || cmd > limits.second) {
        RCLCPP_WARN_THROTTLE(logger(), clock(), UPDATE_LOG_THROTTLE_MS, "[%s] Joint %zu out of limits: %f not in [%f, %f]",
                             name.c_str(), i, cmd, limits.first, limits.second);
        cmd = std::max(limits.first, std::min(limits.second, cmd));
        notifyOutOfLimits = true;
      }

      (void)command_interfaces_[i].set_value(cmd);
    }
  }

  if (pub && (nowNs - lastStatePublishNs) * 1e-9 > statePublishThrottle) {
    if (isActive) {
      updateStatus(msg.status);
      if (notifyOutOfLimits) {
        msg.status = JointPositions::CMD_OUT_OF_LIMITS;
        notifyOutOfLimits = false;
      }
    }
    pub->publish(msg);
    lastStatePublishNs = nowNs;
  }

  return controller_interface::return_type::OK;
}

}  // namespace tiago_telepresence_controllers
