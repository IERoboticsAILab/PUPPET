#!/usr/bin/env python3
"""OptiTrack rigid-body pose -> nav_msgs/Odometry for Unity (ROS 2).

One node for what were two ROS 1 scripts with the same maths (puppet_bringup/scripts/
pose_to_odom.py and puck_pose_to_odom.py):
  - position: marker position minus (offset_x, offset_y); z either locked to the first value
    (TIAGo base, lock_height:=true) or z - offset_z (puck, which TIAGo can lift);
  - yaw only: median of the last 10 yaws (unwrapped), relative to the yaw at startup;
    the first message only sets that reference and is not published.
Output frame "odom", child frame `child_frame_id` ("base_link" or "puck").
"""

import math

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node


def yaw_from_quaternion(x, y, z, w):
    # Same as tf.transformations.euler_from_quaternion(..., 'sxyz')[2]
    return math.atan2(2.0 * (w * z + x * y), w * w + x * x - y * y - z * z)


class YawFilter:
    def __init__(self, window=10):
        self.window = window
        self.buffer = []
        self.initial = None

    def update(self, raw_yaw):
        """Returns the smoothed yaw relative to the first one, or None for the first sample."""
        self.buffer.append(raw_yaw)
        if len(self.buffer) > self.window:
            self.buffer.pop(0)
        smooth = float(np.median(np.unwrap(np.array(self.buffer))))
        if self.initial is None:
            self.initial = smooth
            return None
        rel = smooth - self.initial
        return math.atan2(math.sin(rel), math.cos(rel))


class PoseToOdom(Node):
    def __init__(self):
        super().__init__("optitrack_pose_to_odom")
        self.input_topic = self.declare_parameter("input_topic", "/natnet_ros/umh_tiago_base/pose").value
        self.output_topic = self.declare_parameter("output_topic", "/odom_mocap").value
        self.child_frame = self.declare_parameter("child_frame_id", "base_link").value
        self.lock_height = self.declare_parameter("lock_height", True).value
        self.offset = [self.declare_parameter(f"offset_{a}", 0.0).value for a in "xyz"]
        self.fixed_height = None
        self.yaw = YawFilter()
        self.pub = self.create_publisher(Odometry, self.output_topic, 1)
        self.create_subscription(PoseStamped, self.input_topic, self.on_pose, 1)
        self.get_logger().info(f"{self.input_topic} -> {self.output_topic} ({self.child_frame})")
        self.create_timer(5.0, self.watchdog)
        self.received = False

    def watchdog(self):
        if not self.received:
            self.get_logger().warn(
                f"no data on {self.input_topic} yet: is the rigid body tracked and streaming in Motive? "
                f"(`ros2 topic list | grep natnet_ros` shows the names actually published)")

    def on_pose(self, msg):
        self.received = True
        p, q = msg.pose.position, msg.pose.orientation
        if self.lock_height:
            if self.fixed_height is None:
                self.fixed_height = p.z
                self.get_logger().info(f"locked fixed height at {self.fixed_height:.4f}")
            z = self.fixed_height
        else:
            z = p.z - self.offset[2]

        rel = self.yaw.update(yaw_from_quaternion(q.x, q.y, q.z, q.w))
        if rel is None:
            self.get_logger().info(f"initialized starting yaw at {math.degrees(self.yaw.initial):.2f} deg")
            return

        odom = Odometry()
        odom.header.stamp = self.get_clock().now().to_msg()
        odom.header.frame_id = "odom"
        odom.child_frame_id = self.child_frame
        odom.pose.pose.position.x = p.x - self.offset[0]
        odom.pose.pose.position.y = p.y - self.offset[1]
        odom.pose.pose.position.z = z
        odom.pose.pose.orientation.z = math.sin(rel / 2.0)
        odom.pose.pose.orientation.w = math.cos(rel / 2.0)
        self.pub.publish(odom)


def main():
    rclpy.init()
    node = PoseToOdom()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
