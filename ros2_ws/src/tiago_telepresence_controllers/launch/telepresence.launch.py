"""PUPPET telepresence on TIAGo (ROS 2): what tiago_real.launch did on ROS 1.

    ros2 launch tiago_telepresence_controllers telepresence.launch.py [tcp_port:=10000] [motion:=]

Starts, on TIAGo:
  - ROS-TCP-Endpoint (Unity connects here),
  - the four *_tp_controller (loaded inactive into PAL's controller_manager),
  - tp_controller_switcher (activates them; Ctrl+C hands the joints back to PAL),
  - tp_arm_motion (/tp_arm_motion/command, the Quest's extend-arm button).
PlayMotion2 is PAL's and already runs on 25.01; it is not started here.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

TP_CONTROLLERS = ["arm_tp_controller", "gripper_tp_controller", "torso_tp_controller", "head_tp_controller"]


def generate_launch_description():
    tcp_ip = LaunchConfiguration("tcp_ip")
    tcp_port = LaunchConfiguration("tcp_port")
    motion = LaunchConfiguration("motion")
    params = PathJoinSubstitution([FindPackageShare("tiago_telepresence_controllers"), "config", "telepresence_controllers.yaml"])

    # puppet_endpoint.py = ROS-TCP-Endpoint with best-effort subscriptions (see the script).
    # No `name=`: the endpoint runs one node per topic, and a name remap would give them all the same name.
    endpoint = Node(
        package="tiago_telepresence_controllers",
        executable="puppet_endpoint.py",
        emulate_tty=True,
        output="screen",
        parameters=[{"ROS_IP": tcp_ip, "ROS_TCP_PORT": tcp_port}],
    )

    spawner = Node(
        package="controller_manager",
        executable="spawner",
        name="telepresence_controllers_spawner",
        output="screen",
        arguments=TP_CONTROLLERS + ["--inactive", "--param-file", params,
                                    "--controller-manager", "/controller_manager",
                                    "--controller-manager-timeout", "30"],
    )

    switcher = Node(
        package="tiago_telepresence_controllers",
        executable="tp_controller_switcher.py",
        name="tp_controller_switcher",
        output="screen",
        emulate_tty=True,
    )

    arm_motion = Node(
        package="tiago_telepresence_controllers",
        executable="arm_motion.py",
        name="tp_arm_motion",
        output="screen",
        emulate_tty=True,
        arguments=["--motion", motion],
    )

    return LaunchDescription([
        DeclareLaunchArgument("tcp_ip", default_value="0.0.0.0", description="address ROS-TCP-Endpoint listens on"),
        DeclareLaunchArgument("tcp_port", default_value="10000", description="port Unity connects to"),
        DeclareLaunchArgument("motion", default_value="", description="PlayMotion2 motion to play once tp_arm_motion is up"),
        endpoint,
        spawner,
        # The switcher and arm_motion need the tp controllers loaded; start them once the spawner is done.
        RegisterEventHandler(OnProcessExit(target_action=spawner, on_exit=[switcher, arm_motion])),
    ])
