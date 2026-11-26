// Head, torso and gripper telepresence controllers (ports of head_tp_controller.cpp,
// torso_tp_controller.cpp and gripper_tp_controller.cpp; same behaviour).

#include <geometry_msgs/msg/quaternion_stamped.hpp>
#include <kdl/frames.hpp>
#include <pluginlib/class_list_macros.hpp>
#include <std_msgs/msg/int32.hpp>

#include "tiago_telepresence_controllers/generic_tp_controller.hpp"

namespace tiago_telepresence_controllers
{

// Headset orientation -> head pan/tilt.
class HeadController : public JointBufferController<geometry_msgs::msg::QuaternionStamped>
{
public:
  HeadController() : JointBufferController("head"), q(2) {}

protected:
  void processData(const geometry_msgs::msg::QuaternionStamped & msg) override
  {
    const auto rot = KDL::Rotation::Quaternion(msg.quaternion.x, msg.quaternion.y, msg.quaternion.z, msg.quaternion.w);
    double alpha, beta, gamma;
    rot.GetEulerZYX(alpha, beta, gamma);  // R_z_alpha * R_y_beta * R_x_gamma
    q(0) = -beta;
    q(1) = -gamma;
    accept(q, msg.header.stamp);
  }

private:
  KDL::JntArray q;
};

// -1 / 0 / +1 from the controller buttons -> torso up/down by `step` per update.
class TorsoController : public StepperController<std_msgs::msg::Int32>
{
public:
  TorsoController() : StepperController("torso") {}

protected:
  void processData(const std_msgs::msg::Int32 & msg) override
  {
    accept({static_cast<double>(msg.data)});
  }
};

// -1 / 0 / +1 -> both fingers open/close by `step` per update.
class GripperController : public StepperController<std_msgs::msg::Int32>
{
public:
  GripperController() : StepperController("gripper") {}

protected:
  void processData(const std_msgs::msg::Int32 & msg) override
  {
    const auto value = static_cast<double>(msg.data);
    accept({value, value});
  }
};

}  // namespace tiago_telepresence_controllers

PLUGINLIB_EXPORT_CLASS(tiago_telepresence_controllers::HeadController, controller_interface::ControllerInterface)
PLUGINLIB_EXPORT_CLASS(tiago_telepresence_controllers::TorsoController, controller_interface::ControllerInterface)
PLUGINLIB_EXPORT_CLASS(tiago_telepresence_controllers::GripperController, controller_interface::ControllerInterface)
