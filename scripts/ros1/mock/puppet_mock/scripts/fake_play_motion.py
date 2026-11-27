#!/usr/bin/env python3
"""Stand-in for PAL's PlayMotion (/play_motion action server) on the mock TIAGo.

Like the real one, it plays /play_motion/motions/<name> through PAL's trajectory controllers, and
fails with "No controller was found for joint ..." when the controller owning a joint is not
running (for example while the telepresence controllers hold the arm). No approach planning:
the motion takes time_from_start x ~slowdown.
"""
import actionlib
import rospy
from control_msgs.msg import FollowJointTrajectoryAction, FollowJointTrajectoryGoal
from controller_manager_msgs.srv import ListControllers
from play_motion_msgs.msg import PlayMotionAction, PlayMotionResult
from trajectory_msgs.msg import JointTrajectoryPoint

OWNER = {"torso_lift_joint": "torso_controller", "head_1_joint": "head_controller", "head_2_joint": "head_controller"}
OWNER.update({"arm_%d_joint" % i: "arm_controller" for i in range(1, 8)})


def execute(goal):
    res = PlayMotionResult()
    key = "/play_motion/motions/%s" % goal.motion_name
    if not rospy.has_param(key):
        res.error_code, res.error_string = PlayMotionResult.MOTION_NOT_FOUND, "Motion '%s' not found" % goal.motion_name
        return server.set_aborted(res)
    motion = rospy.get_param(key)
    slowdown = rospy.get_param("~slowdown", 1.0)  # read per goal, so a test can slow motions down
    states = {c.name: c.state for c in list_controllers().controller}
    groups = {}
    for i, joint in enumerate(motion["joints"]):
        ctrl = OWNER.get(joint)
        if ctrl is None or states.get(ctrl) != "running":
            res.error_code = PlayMotionResult.OTHER_ERROR
            res.error_string = "No controller was found for joint '%s'" % joint
            rospy.logerr(res.error_string)
            return server.set_aborted(res)
        groups.setdefault(ctrl, []).append(i)
    rospy.loginfo("Playing '%s'", goal.motion_name)
    clients = []
    for ctrl, idx in groups.items():
        g = FollowJointTrajectoryGoal()
        g.trajectory.joint_names = [motion["joints"][i] for i in idx]
        for p in motion["points"]:
            g.trajectory.points.append(JointTrajectoryPoint(positions=[p["positions"][i] for i in idx],
                                                            time_from_start=rospy.Duration(p["time_from_start"] * slowdown)))
        c = trajectory_clients[ctrl]
        c.send_goal(g)
        clients.append(c)
    for c in clients:
        while not c.wait_for_result(rospy.Duration(0.1)):
            if server.is_preempt_requested():
                for cc in clients:
                    cc.cancel_goal()
                rospy.logwarn("'%s' canceled", goal.motion_name)
                return server.set_preempted()
    rospy.loginfo("'%s' done", goal.motion_name)
    res.error_code = PlayMotionResult.SUCCEEDED
    server.set_succeeded(res)


rospy.init_node("play_motion")
rospy.wait_for_service("/controller_manager/list_controllers")
list_controllers = rospy.ServiceProxy("/controller_manager/list_controllers", ListControllers)
trajectory_clients = {}
for name in set(OWNER.values()):
    trajectory_clients[name] = actionlib.SimpleActionClient("/%s/follow_joint_trajectory" % name, FollowJointTrajectoryAction)
    trajectory_clients[name].wait_for_server()
server = actionlib.SimpleActionServer("/play_motion", PlayMotionAction, execute, auto_start=False)
server.start()
rospy.loginfo("fake play_motion ready")
rospy.spin()
