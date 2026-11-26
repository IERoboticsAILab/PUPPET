// Unit tests for the command buffer (no ROS, no robot): the joint buffer replays commands with
// a delay and interpolates linearly; the frame buffer stays on the commanded path.

#include <gtest/gtest.h>

#include <chrono>
#include <thread>

#include "tiago_telepresence_controllers/command_buffer.hpp"

using tiago_telepresence_controllers::FrameCommandBuffer;
using tiago_telepresence_controllers::JointCommandBuffer;

namespace
{
KDL::JntArray jnt(double v)
{
  KDL::JntArray q(1);
  q(0) = v;
  return q;
}
}  // namespace

TEST(JointCommandBuffer, HoldsInitialValueUntilFilled)
{
  JointCommandBuffer buffer("test", 2, 1);
  buffer.reset(jnt(0.5));
  EXPECT_DOUBLE_EQ(buffer.interpolate()(0), 0.5);
  buffer.accept(jnt(1.0), 0.0);
  EXPECT_DOUBLE_EQ(buffer.interpolate()(0), 0.5);  // not enough commands buffered yet
}

TEST(JointCommandBuffer, InterpolatesBetweenCommands)
{
  const int minSize = 2;
  JointCommandBuffer buffer("test", minSize, 1);
  buffer.reset(jnt(0.0));

  // A ramp: value == time, one command every 10 ms (stamps need not be wall time).
  const double dt = 0.01;
  int n = 0;
  for (; n < minSize * 3; n++) {
    buffer.accept(jnt(n * dt), n * dt);
  }

  double previous = -1.0;
  for (int i = 0; i < 5; i++, n++) {
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
    buffer.accept(jnt(n * dt), n * dt);
    const double value = buffer.interpolate()(0);
    EXPECT_GE(value, previous) << "ramp must not go backwards";
    EXPECT_LE(value, n * dt) << "never ahead of the newest command";
    previous = value;
  }
}

TEST(FrameCommandBuffer, StaysOnSegment)
{
  const int minSize = 2;
  FrameCommandBuffer buffer("test", minSize);
  buffer.reset(KDL::Frame::Identity());

  const double dt = 0.01;
  int n = 0;
  for (; n < minSize * 6 + 1; n++) {
    buffer.accept(KDL::Frame(KDL::Vector(n * 0.001, 0, 0)), n * dt);
  }

  std::this_thread::sleep_for(std::chrono::milliseconds(5));
  const auto H = buffer.interpolate();
  EXPECT_NEAR(H.p.y(), 0.0, 1e-9);
  EXPECT_NEAR(H.p.z(), 0.0, 1e-9);
  EXPECT_GE(H.p.x(), 0.0);
  EXPECT_LE(H.p.x(), n * 0.001);
}
