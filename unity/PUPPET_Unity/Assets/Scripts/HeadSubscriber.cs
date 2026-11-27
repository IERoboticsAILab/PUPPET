using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Std;
using UnityEngine.InputSystem;

public class HeadSubscriber : MonoBehaviour
{
    private ROSConnection ros;

    public InputActionReference headReference = null;

    public string topicName = "/head_controller/state";

    private Vector3 headOrientation;

    void Start()
    {
        ros = ROSConnection.GetOrCreateInstance();
#if ROS2
        // PAL's /head_controller/state is control_msgs/JointTrajectoryControllerState, not
        // Float32MultiArray, so this never received data (silent on ROS 1, a type conflict on ROS 2).
        // headOrientation is not used anywhere, so the ROS 2 build does not subscribe.
#else
        ros.Subscribe<Float32MultiArrayMsg>(topicName, StateCallback);
#endif
    }

    void StateCallback(Float32MultiArrayMsg msg)
    {
        headOrientation = new(msg.data[0], msg.data[1], .0f);
    }

    void Update()
    {
        //Debug.Log($"head: {headOrientation}");
    }
}
