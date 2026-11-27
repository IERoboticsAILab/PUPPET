#!/usr/bin/env python3
"""Mock natnet_ros: /natnet_ros/<body>/pose at 120 Hz for each body in ~bodies (space separated)."""
import rospy
from geometry_msgs.msg import PoseStamped

rospy.init_node("natnet_ros")
pubs = {b: rospy.Publisher("~%s/pose" % b, PoseStamped, queue_size=10) for b in rospy.get_param("~bodies").split()}
rate = rospy.Rate(120)
while not rospy.is_shutdown():
    for i, (body, pub) in enumerate(pubs.items()):
        m = PoseStamped()
        m.header.stamp, m.header.frame_id = rospy.Time.now(), "world"
        m.pose.position.x, m.pose.orientation.w = 1.0 + i, 1.0
        pub.publish(m)
    rate.sleep()
