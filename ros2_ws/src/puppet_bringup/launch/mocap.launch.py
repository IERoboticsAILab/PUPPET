"""archimedes side of PUPPET on ROS 2 (what mocap.launch did on ROS 1):
NatNet -> /natnet_ros/<rigid body>/pose, then TIAGo base -> /odom_mocap and puck -> /puck_mocap.

    ros2 launch puppet_bringup mocap.launch.py server_ip:=10.205.3.3 client_ip:=10.205.3.122
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration as C
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("server_ip", default_value="10.205.3.3", description="Motive (gaia)"),
        DeclareLaunchArgument("client_ip", default_value="10.205.3.122", description="this machine"),
        DeclareLaunchArgument("base_topic", default_value="/natnet_ros/umh_tiago_base/pose"),
        DeclareLaunchArgument("puck_topic", default_value="/natnet_ros/umh_object_mahika/pose"),
        Node(package="natnet_bridge", executable="natnet_bridge", name="natnet_ros", output="screen",
             parameters=[{"server_ip": C("server_ip"), "client_ip": C("client_ip"), "global_frame": "world"}]),
        Node(package="puppet_bringup", executable="mocap_pose_to_odom.py", name="optitrack_pose_to_odom", output="screen",
             parameters=[{"input_topic": C("base_topic"), "output_topic": "/odom_mocap",
                          "child_frame_id": "base_link", "lock_height": True}]),
        Node(package="puppet_bringup", executable="mocap_pose_to_odom.py", name="puck_pose_to_odom", output="screen",
             parameters=[{"input_topic": C("puck_topic"), "output_topic": "/puck_mocap",
                          "child_frame_id": "puck", "lock_height": False}]),
    ])
