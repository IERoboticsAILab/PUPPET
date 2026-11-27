// Controller templates shared by the four telepresence controllers (port of the ROS 1
// generic_tp_controller.hpp, same logic).

#ifndef TIAGO_TELEPRESENCE_CONTROLLERS__GENERIC_TP_CONTROLLER_HPP_
#define TIAGO_TELEPRESENCE_CONTROLLERS__GENERIC_TP_CONTROLLER_HPP_

#include <algorithm>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include <builtin_interfaces/msg/time.hpp>

#include "tiago_telepresence_controllers/command_buffer.hpp"
#include "tiago_telepresence_controllers/controller_base.hpp"

namespace tiago_telepresence_controllers
{

inline KDL::JntArray jointVectorToKdl(const std::vector<double> & v)
{
  KDL::JntArray ret(v.size());
  ret.data = Eigen::VectorXd::Map(v.data(), v.size());
  return ret;
}

inline std::vector<double> kdlToJointVector(const KDL::JntArray & q)
{
  const auto & priv = q.data;
  return std::vector<double>(priv.data(), priv.data() + priv.rows());
}

inline double stampToSec(const builtin_interfaces::msg::Time & t)
{
  return t.sec + t.nanosec * 1e-9;
}

template<typename T>
class GenericController : public ControllerBase
{
public:
  using ControllerBase::ControllerBase;

protected:
  void registerSubscriber() final
  {
    // Queue of 1, as in ROS 1: only the newest command matters.
    sub = get_node()->template create_subscription<T>(
      "~/command", rclcpp::QoS(1),
      [this](const std::shared_ptr<const T> msg) {
        updateStamp();
        processData(*msg);
      });
  }

  virtual void processData(const T & msg) = 0;

private:
  typename rclcpp::Subscription<T>::SharedPtr sub;
};

template<typename T, typename B>
class BufferedController : public GenericController<T>
{
public:
  using GenericController<T>::GenericController;

protected:
  void declareParameters() override
  {
    this->template auto_declare<int>("buffer_min_size", 0);
  }

  bool additionalSetup(const std::string &) override
  {
    const auto bufferMinSize = this->get_node()->get_parameter("buffer_min_size").as_int();

    if (bufferMinSize <= 0) {
      RCLCPP_ERROR(this->logger(), "[%s] buffer_min_size must be greater than 0", this->getName().c_str());
      return false;
    }

    buffer = makeBuffer(static_cast<int>(bufferMinSize));
    return true;
  }

  void onStarting(const std::vector<double> & angles) override
  {
    const auto initialValue = convertToBufferType(angles);
    std::lock_guard<std::mutex> lock(bufferMutex);
    buffer->reset(initialValue);
  }

  void accept(const typename B::ValueType & command, const builtin_interfaces::msg::Time & stamp)
  {
    std::lock_guard<std::mutex> lock(bufferMutex);
    if (buffer) {buffer->accept(command, stampToSec(stamp));}
  }

  typename B::WarnFn warner()
  {
    auto logger = this->logger();
    return [logger](const std::string & what) {RCLCPP_WARN(logger, "%s", what.c_str());};
  }

  virtual std::unique_ptr<B> makeBuffer(int size) = 0;
  virtual typename B::ValueType convertToBufferType(const std::vector<double> & v) = 0;
  virtual std::vector<double> convertToVector(const KDL::JntArray & q, const typename B::ValueType & v, double period) = 0;

private:
  std::vector<double> getDesiredJointValues(const std::vector<double> & current, double period) final
  {
    std::lock_guard<std::mutex> lock(bufferMutex);
    const auto value = buffer->interpolate();
    return convertToVector(jointVectorToKdl(current), value, period);
  }

  std::unique_ptr<B> buffer;
  mutable std::mutex bufferMutex;
};

template<typename T>
class JointBufferController : public BufferedController<T, JointCommandBuffer>
{
public:
  using BufferedController<T, JointCommandBuffer>::BufferedController;

protected:
  std::unique_ptr<JointCommandBuffer> makeBuffer(int size) override
  {
    return std::make_unique<JointCommandBuffer>(this->getName(), size, this->numJoints(), this->warner());
  }

  KDL::JntArray convertToBufferType(const std::vector<double> & v) override
  {
    return jointVectorToKdl(v);
  }

  std::vector<double> convertToVector(const KDL::JntArray &, const KDL::JntArray & v, double) override
  {
    return kdlToJointVector(v);
  }
};

template<typename T>
class FrameBufferController : public BufferedController<T, FrameCommandBuffer>
{
public:
  using BufferedController<T, FrameCommandBuffer>::BufferedController;

protected:
  std::unique_ptr<FrameCommandBuffer> makeBuffer(int size) override
  {
    return std::make_unique<FrameCommandBuffer>(this->getName(), size, this->warner());
  }
};

// Adds `step` * command to the current position on every update (torso and gripper buttons).
template<typename T>
class StepperController : public GenericController<T>
{
public:
  using GenericController<T>::GenericController;

protected:
  void declareParameters() override
  {
    this->template auto_declare<double>("step", 0.0);
  }

  bool additionalSetup(const std::string &) override
  {
    step = this->get_node()->get_parameter("step").as_double();

    if (step <= 0.0) {
      RCLCPP_ERROR(this->logger(), "[%s] step must be greater than 0", this->getName().c_str());
      return false;
    }

    std::lock_guard<std::mutex> lock(storageMutex);
    stored.assign(this->numJoints(), 0.0);
    return true;
  }

  void accept(const std::vector<double> & command)
  {
    std::lock_guard<std::mutex> lock(storageMutex);
    stored = command;
  }

private:
  std::vector<double> getDesiredJointValues(const std::vector<double> & current, double) final
  {
    std::vector<double> desired(current.size());
    std::lock_guard<std::mutex> lock(storageMutex);
    std::transform(current.cbegin(), current.cend(), stored.cbegin(), desired.begin(),
                   [this](double c, double s) {return c + step * s;});
    return desired;
  }

  double step {0.0};
  std::vector<double> stored;
  mutable std::mutex storageMutex;
};

}  // namespace tiago_telepresence_controllers

#endif  // TIAGO_TELEPRESENCE_CONTROLLERS__GENERIC_TP_CONTROLLER_HPP_
