// Command buffer for the telepresence controllers: smooths the irregular stream of commands that
// arrive from Unity over WiFi by replaying them with a fixed delay and interpolating between them.
//
// Port of ros_ws/src/tiago_telepresence_controllers/include/command_buffer.hpp with the same
// algorithm. The only change: times are plain seconds on std::chrono::steady_clock instead of
// ros::SteadyTime, and warnings go through a callback, so this header has no ROS dependency.

#ifndef TIAGO_TELEPRESENCE_CONTROLLERS__COMMAND_BUFFER_HPP_
#define TIAGO_TELEPRESENCE_CONTROLLERS__COMMAND_BUFFER_HPP_

#include <chrono>
#include <functional>
#include <iterator>
#include <list>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include <kdl/frames.hpp>
#include <kdl/jntarray.hpp>
#include <kdl/trajectory.hpp>

namespace tiago_telepresence_controllers
{

constexpr int CAPACITY_MULTIPLIER = 5;

inline double steadyNow()
{
  using namespace std::chrono;
  return duration<double>(steady_clock::now().time_since_epoch()).count();
}

template<typename T>
class CommandBufferBase
{
public:
  using ValueType = T;
  using WarnFn = std::function<void(const std::string &)>;

  CommandBufferBase(const std::string & name, int minSize, WarnFn warn = nullptr)
  : name(name), minSize(minSize), warn(std::move(warn))
  {}

  virtual ~CommandBufferBase() = default;

  // timestamp: seconds, any clock, as long as it is consistent between commands (only the
  // differences between commands are used).
  void accept(const T & command, double timestamp)
  {
    buffer.emplace_back(command, timestamp);

    if (buffer.size() > static_cast<std::size_t>(minSize * (CAPACITY_MULTIPLIER + 1))) {
      if (left == buffer.begin()) {
        // undesirable, but we need to keep our iterators valid
        std::advance(left, 1);
        std::advance(right, 1);
        doWarn("Reached buffer front");
      }

      buffer.pop_front();

      if (!enabled) {
        if (left == right) {
          std::advance(right, 1);
          left->second = right->second;
        }

        update();
        offset = steadyNow() - left->second;
        enabled = true;
      }
    }
  }

  T interpolate()
  {
    const auto refTime = steadyNow() - offset;

    if (enabled && !buffer.empty() && left->second <= refTime) {
      bool needsUpdate = false;

      while (right != buffer.end() && right->second < refTime) {
        std::advance(left, 1);
        std::advance(right, 1);
        needsUpdate = true;
      }

      if (right != buffer.end()) {
        if (needsUpdate) {
          update();
        }

        return interpolateInternal(refTime - left->second);
      }

      doWarn("Reached buffer rear");
      right = left;
    }

    enabled = false;
    return right->first;
  }

  double getCommandPeriod() const
  {
    return !buffer.empty() ? (right->second - left->second) : 0.0;
  }

  void reset(const T & initialCommand)
  {
    offset = 0.0;
    buffer.assign(minSize * CAPACITY_MULTIPLIER, std::make_pair(initialCommand, 0.0));

    left = right = buffer.end();
    std::advance(left, -1);
    std::advance(right, -1);

    enabled = false;
    resetInternal();
  }

protected:
  using BufferType = std::list<std::pair<T, double>>;

  virtual void update() = 0;
  virtual T interpolateInternal(double t) = 0;
  virtual void resetInternal() {}

  typename BufferType::iterator left;
  typename BufferType::iterator right;

private:
  void doWarn(const std::string & what) const
  {
    if (warn) {warn("[" + name + "] " + what);}
  }

  const std::string name;
  const int minSize {0};
  WarnFn warn;
  BufferType buffer;
  double offset {0.0};
  bool enabled {false};
};

class JointCommandBuffer : public CommandBufferBase<KDL::JntArray>
{
public:
  JointCommandBuffer(const std::string & name, int minSize, int cmdSize, WarnFn warn = nullptr)
  : CommandBufferBase(name, minSize, std::move(warn)), slopes(cmdSize, 0.0)
  {}

protected:
  void update() override;
  KDL::JntArray interpolateInternal(double t) override;
  void resetInternal() override;

private:
  std::vector<double> slopes;
};

class FrameCommandBuffer : public CommandBufferBase<KDL::Frame>
{
public:
  using CommandBufferBase::CommandBufferBase;

protected:
  void update() override;
  KDL::Frame interpolateInternal(double t) override;
  void resetInternal() override;

private:
  std::unique_ptr<KDL::Trajectory> trajectory;
};

}  // namespace tiago_telepresence_controllers

#endif  // TIAGO_TELEPRESENCE_CONTROLLERS__COMMAND_BUFFER_HPP_
