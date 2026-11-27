// Base class of the four telepresence controllers, on ros2_control.
//
// Behaviour is the same as the ROS 1 version (ros_ws/src/tiago_telepresence_controllers):
// - claims the position command interface of each joint in `joint_names`;
// - follows commands from `~/command` (e.g. /arm_tp_controller/command);
// - when no command has arrived for INPUT_TIMEOUT, stops writing and the joints hold;
// - clamps every command to the URDF joint limits;
// - publishes JointPositions on `~/state` every `state_publish_throttle` seconds (0 = off).
// Added for ROS 2: on activation the command interfaces are set to the current positions, so
// the hand-over from PAL's controllers never jumps.

#ifndef TIAGO_TELEPRESENCE_CONTROLLERS__CONTROLLER_BASE_HPP_
#define TIAGO_TELEPRESENCE_CONTROLLERS__CONTROLLER_BASE_HPP_

#include <atomic>
#include <cmath>
#include <limits>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

#include <controller_interface/controller_interface.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp_lifecycle/state.hpp>

#include "tiago_telepresence_controllers/msg/joint_positions.hpp"

namespace tiago_telepresence_controllers
{

constexpr int UPDATE_LOG_THROTTLE_MS = 1000;
constexpr double INPUT_TIMEOUT = 0.25;  // [s]

using CallbackReturn = rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface::CallbackReturn;
using JointPositions = tiago_telepresence_controllers::msg::JointPositions;

// ros2_control 4.x (PAL alum) has get_optional(); older releases only get_value(). Support both.
namespace detail
{
template<typename I>
auto readValue(const I & itf, int) -> decltype(itf.get_optional(), double())
{
  return itf.get_optional().value_or(std::numeric_limits<double>::quiet_NaN());
}
template<typename I>
double readValue(const I & itf, long)
{
  return itf.get_value();
}
}  // namespace detail

template<typename I>
double readValue(const I & itf) {return detail::readValue(itf, 0);}

class ControllerBase : public controller_interface::ControllerInterface
{
public:
  explicit ControllerBase(const std::string & name) : name(name) {}

  CallbackReturn on_init() final;
  controller_interface::InterfaceConfiguration command_interface_configuration() const final;
  controller_interface::InterfaceConfiguration state_interface_configuration() const final;
  CallbackReturn on_configure(const rclcpp_lifecycle::State & previous_state) final;
  CallbackReturn on_activate(const rclcpp_lifecycle::State & previous_state) final;
  CallbackReturn on_deactivate(const rclcpp_lifecycle::State & previous_state) final;
  controller_interface::return_type update(const rclcpp::Time & time, const rclcpp::Duration & period) final;

protected:
  const std::vector<std::pair<double, double>> & getJointLimits() const {return jointLimits;}
  virtual void declareParameters() {}
  virtual bool additionalSetup(const std::string & /*robotDescription*/) {return true;}
  virtual void registerSubscriber() = 0;
  virtual std::vector<double> getDesiredJointValues(const std::vector<double> & current, double period) = 0;
  virtual void onStarting(const std::vector<double> & /*angles*/) {}
  virtual void onDisabling() {}
  virtual void updateStatus(int & /*status*/) {}
  void updateStamp();
  int numJoints() const {return static_cast<int>(jointNames.size());}
  const std::string & getName() const {return name;}
  rclcpp::Logger logger() const {return get_node()->get_logger();}
  rclcpp::Clock & clock() {return *get_node()->get_clock();}

private:
  std::string name;
  std::vector<std::string> jointNames;
  std::vector<std::pair<double, double>> jointLimits;
  rclcpp::Publisher<JointPositions>::SharedPtr pub;
  double statePublishThrottle {0.0};
  int64_t lastStatePublishNs {0};
  bool isActive {false};
  bool notifyOutOfLimits {false};
  std::atomic<int64_t> stampNs {0};  // when the last command arrived (node clock)
};

}  // namespace tiago_telepresence_controllers

#endif  // TIAGO_TELEPRESENCE_CONTROLLERS__CONTROLLER_BASE_HPP_
