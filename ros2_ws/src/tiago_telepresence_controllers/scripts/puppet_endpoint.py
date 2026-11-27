#!/usr/bin/env python3
"""ROS-TCP-Endpoint (main-ros2) for PUPPET, with best-effort subscriptions.

The stock endpoint subscribes on Unity's behalf with QoSProfile(depth=10), which is RELIABLE. A
reliable subscription never matches a BEST_EFFORT publisher (camera drivers usually use sensor-data
QoS), so Unity would silently get nothing. A best-effort subscription matches both kinds, and the
DDS hop is local on TIAGo, so nothing is lost. Publishers and services are not changed.
"""

import sys

import ros_tcp_endpoint.subscriber as subscriber
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from ros_tcp_endpoint.default_server_endpoint import main


def best_effort_profile(*args, **kwargs):
    kwargs.setdefault("reliability", QoSReliabilityPolicy.BEST_EFFORT)
    return QoSProfile(*args, **kwargs)


subscriber.QoSProfile = best_effort_profile

if __name__ == "__main__":
    sys.exit(main())
