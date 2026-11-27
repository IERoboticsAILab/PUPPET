// Arm telepresence controller: headset hand pose -> 7 arm joints through KDL's pseudo-inverse
// velocity IK. Port of ros_ws/.../src/arm_tp_controller.cpp; the maths is unchanged.

#include <atomic>
#include <memory>

#include <geometry_msgs/msg/pose_stamped.hpp>
#include <kdl/chainfksolverpos_recursive.hpp>
#include <kdl/chainiksolvervel_pinv.hpp>
#include <kdl_parser/kdl_parser.hpp>
#include <pluginlib/class_list_macros.hpp>

#include "tiago_telepresence_controllers/generic_tp_controller.hpp"

namespace tiago_telepresence_controllers
{

class ArmController : public FrameBufferController<geometry_msgs::msg::PoseStamped>
{
public:
  ArmController() : FrameBufferController("arm") {}

  void onStarting(const std::vector<double> & angles) override
  {
    q = jointVectorToKdl(angles);
    fkSolverPos->JntToCart(q, H_0_N_initial);
    RCLCPP_INFO(logger(), "[%s] Initial position: %f %f %f", getName().c_str(),
                H_0_N_initial.p.x(), H_0_N_initial.p.y(), H_0_N_initial.p.z());
    H_0_N_prev = H_0_N_initial;
    FrameBufferController::onStarting(angles);
    active = true;
  }

  void onDisabling() override
  {
    active = false;
    status = JointPositions::CMD_OK;
  }

  void updateStatus(int & out) override
  {
    out = status;
    status = JointPositions::CMD_OK;
  }

protected:
  void declareParameters() override
  {
    FrameBufferController::declareParameters();
    auto_declare<std::string>("start_link", "");
    auto_declare<std::string>("end_link", "");
    auto_declare<double>("ik_solver_vel_eps", 0.0);
    auto_declare<int>("ik_solver_vel_max_iter", 0);
  }

  bool additionalSetup(const std::string & description) override;
  void processData(const geometry_msgs::msg::PoseStamped & msg) override;
  KDL::Frame convertToBufferType(const std::vector<double> & v) override;
  std::vector<double> convertToVector(const KDL::JntArray & q, const KDL::Frame & H_0_N, double period) override;

private:
  bool checkReturnCode(int ret);

  KDL::Chain chain;
  std::unique_ptr<KDL::ChainFkSolverPos_recursive> fkSolverPos;
  std::unique_ptr<KDL::ChainIkSolverVel_pinv> ikSolverVel;

  KDL::Frame H_0_N_initial;
  KDL::Frame H_0_N_prev;
  KDL::JntArray q;

  std::atomic_bool active {false};
  std::atomic_int32_t status {JointPositions::CMD_OK};
};

bool ArmController::additionalSetup(const std::string & description)
{
  KDL::Tree tree;
  if (!kdl_parser::treeFromString(description, tree)) {
    RCLCPP_ERROR(logger(), "[%s] Failed to construct KDL tree", getName().c_str());
    return false;
  }

  const auto startLink = get_node()->get_parameter("start_link").as_string();
  const auto endLink = get_node()->get_parameter("end_link").as_string();
  if (startLink.empty() || endLink.empty()) {
    RCLCPP_ERROR(logger(), "[%s] start_link and end_link must be set", getName().c_str());
    return false;
  }

  if (!tree.getChain(startLink, endLink, chain)) {
    RCLCPP_ERROR(logger(), "[%s] No chain %s -> %s in the URDF", getName().c_str(), startLink.c_str(), endLink.c_str());
    return false;
  }

  RCLCPP_INFO(logger(), "[%s] Got chain with %d joints and %d segments", getName().c_str(),
              chain.getNrOfJoints(), chain.getNrOfSegments());

  if (static_cast<int>(chain.getNrOfJoints()) != numJoints()) {
    RCLCPP_ERROR(logger(), "[%s] Chain has %d joints but joint_names lists %d", getName().c_str(),
                 chain.getNrOfJoints(), numJoints());
    return false;
  }

  const auto epsVel = get_node()->get_parameter("ik_solver_vel_eps").as_double();
  const auto maxIterVel = get_node()->get_parameter("ik_solver_vel_max_iter").as_int();
  if (epsVel <= 0.0 || maxIterVel <= 0) {
    RCLCPP_ERROR(logger(), "[%s] ik_solver_vel_eps and ik_solver_vel_max_iter must be greater than 0", getName().c_str());
    return false;
  }

  fkSolverPos = std::make_unique<KDL::ChainFkSolverPos_recursive>(chain);
  ikSolverVel = std::make_unique<KDL::ChainIkSolverVel_pinv>(chain, epsVel, static_cast<int>(maxIterVel));

  return FrameBufferController::additionalSetup(description);
}

void ArmController::processData(const geometry_msgs::msg::PoseStamped & msg)
{
  if (active) {
    // change in pose between initial and desired, referred to the TCP on its initial pose
    KDL::Frame H_N(
      KDL::Rotation::Quaternion(msg.pose.orientation.x, msg.pose.orientation.y, msg.pose.orientation.z, msg.pose.orientation.w),
      KDL::Vector(msg.pose.position.x, msg.pose.position.y, msg.pose.position.z));

    accept(H_0_N_initial * H_N, msg.header.stamp);
  }
}

KDL::Frame ArmController::convertToBufferType(const std::vector<double> & v)
{
  KDL::Frame H;
  fkSolverPos->JntToCart(jointVectorToKdl(v), H);
  return H;
}

std::vector<double> ArmController::convertToVector(const KDL::JntArray &, const KDL::Frame & H_0_N, double period)
{
  // refer to base frame, but leave the reference point intact (H_0_N_initial, as in ROS 1)
  const auto twist = H_0_N_initial.M * KDL::diff(H_0_N_prev, H_0_N, period);

  KDL::JntArray qdot(q.rows());

  if (!checkReturnCode(ikSolverVel->CartToJnt(q, twist, qdot))) {
    RCLCPP_WARN_THROTTLE(logger(), clock(), UPDATE_LOG_THROTTLE_MS,
                         "[%s] Stored configuration is singular, will attempt to move anyway", getName().c_str());
  }

  // look ahead in case the desired motion would place us in a singular point
  KDL::JntArray q_temp(q);

  for (unsigned int i = 0; i < q.rows(); i++) {
    q_temp(i) += qdot(i) * period;
  }

  if (checkReturnCode(ikSolverVel->CartToJnt(q_temp, twist, qdot))) {
    // no singular point, so update the calculated joint configuration and pose
    q = q_temp;
    H_0_N_prev = H_0_N;
  }

  return kdlToJointVector(q);
}

bool ArmController::checkReturnCode(int ret)
{
  if (ret == KDL::SolverI::E_NOERROR) {
    return true;
  }

  int code;

  switch (ret) {
    case KDL::ChainIkSolverVel_pinv::E_CONVERGE_PINV_SINGULAR:
      RCLCPP_WARN_THROTTLE(logger(), clock(), UPDATE_LOG_THROTTLE_MS, "[%s] Convergence issue: pseudo-inverse is singular", getName().c_str());
      code = JointPositions::CMD_SINGULARITY;
      break;
    case KDL::SolverI::E_SVD_FAILED:
      RCLCPP_ERROR_THROTTLE(logger(), clock(), UPDATE_LOG_THROTTLE_MS, "[%s] Convergence issue: SVD failed", getName().c_str());
      code = JointPositions::CMD_CONVERGENCE;
      break;
    default:
      RCLCPP_WARN_THROTTLE(logger(), clock(), UPDATE_LOG_THROTTLE_MS, "[%s] Convergence issue: unknown error", getName().c_str());
      code = JointPositions::CMD_UNKNOWN_ERROR;
      break;
  }

  if (status == JointPositions::CMD_OK || status > code) {
    status = code;
  }

  return false;
}

}  // namespace tiago_telepresence_controllers

PLUGINLIB_EXPORT_CLASS(tiago_telepresence_controllers::ArmController, controller_interface::ControllerInterface)
