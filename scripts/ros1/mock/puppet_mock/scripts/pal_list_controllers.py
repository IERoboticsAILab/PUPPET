#!/usr/bin/env python3
"""/controller_manager/list_controllers as TIAGo's Gallium reports it.

Stock Noetic says "initialized" for a controller that was loaded but never started; TIAGo
(Gallium) says "stopped", and PUPPET's tp_controller_switcher.py only starts "stopped" ones (it
worked on the robot on 2026-10-26). fake_hw's own service is remapped to raw_list_controllers;
this node serves the robot's view of it.
"""
import rospy
from controller_manager_msgs.srv import ListControllers, ListControllersResponse

rospy.init_node("pal_list_controllers")
rospy.wait_for_service("/controller_manager/raw_list_controllers")
raw = rospy.ServiceProxy("/controller_manager/raw_list_controllers", ListControllers, persistent=False)


def handle(_req):
    cs = raw().controller
    for c in cs:
        if c.state == "initialized":
            c.state = "stopped"
    return ListControllersResponse(controller=cs)


rospy.Service("/controller_manager/list_controllers", ListControllers, handle)
rospy.spin()
