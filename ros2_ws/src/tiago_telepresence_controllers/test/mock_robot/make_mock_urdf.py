#!/usr/bin/env python3
"""TIAGo 38's URDF (from PAL's tiago_description) with its ros2_control hardware replaced by
mock_components/GenericSystem for the arm, head, torso and gripper joints. Kinematics and joint
limits stay PAL's, so the controllers see exactly what they see on the robot.

    make_mock_urdf.py OUT.urdf
"""

import subprocess
import sys
import xml.etree.ElementTree as ET

# TIAGo 38 (pal_robot_info_tiago_38/config/10_tiago_38_specifics.yaml)
XACRO_ARGS = ["arm_type:=tiago-arm", "end_effector:=pal-gripper", "ft_sensor:=no-ft-sensor",
              "laser_model:=hokuyo", "camera_model:=orbbec-astra", "base_type:=pmb2", "wrist_model:=wrist-2017"]
# Start pose: PAL's "home"-like tucked arm, torso low, gripper half open.
JOINTS = {
    "torso_lift_joint": 0.15,
    "arm_1_joint": 0.20, "arm_2_joint": -1.34, "arm_3_joint": -0.20, "arm_4_joint": 1.94,
    "arm_5_joint": -1.57, "arm_6_joint": 1.37, "arm_7_joint": 0.0,
    "head_1_joint": 0.0, "head_2_joint": 0.0,
    "gripper_left_finger_joint": 0.02, "gripper_right_finger_joint": 0.02,
}


def main(out):
    from ament_index_python.packages import get_package_share_directory
    xacro = get_package_share_directory("tiago_description") + "/robots/tiago.urdf.xacro"
    urdf = subprocess.run(["xacro", xacro] + XACRO_ARGS, check=True, capture_output=True, text=True).stdout
    root = ET.fromstring(urdf)
    for rc in root.findall("ros2_control"):
        root.remove(rc)
    rc = ET.SubElement(root, "ros2_control", name="MockTiago", type="system")
    hw = ET.SubElement(rc, "hardware")
    ET.SubElement(hw, "plugin").text = "mock_components/GenericSystem"
    ET.SubElement(hw, "param", name="calculate_dynamics").text = "false"
    for name, q0 in JOINTS.items():
        j = ET.SubElement(rc, "joint", name=name)
        ET.SubElement(j, "command_interface", name="position")
        s = ET.SubElement(j, "state_interface", name="position")
        ET.SubElement(s, "param", name="initial_value").text = str(q0)
        ET.SubElement(j, "state_interface", name="velocity")
    with open(out, "w") as f:
        f.write(ET.tostring(root, encoding="unicode"))


if __name__ == "__main__":
    main(sys.argv[1])
