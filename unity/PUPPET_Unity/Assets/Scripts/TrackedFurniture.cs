using UnityEngine;
using Unity.Robotics.ROSTCPConnector;
using RosMessageTypes.Geometry;

// Moves a piece of lab furniture (table, shelf) with its OptiTrack rigid body.
//
// The pose comes straight from natnet_ros (/natnet_ros/<Motive name>/pose). Motive streams
// Z-up, so ROS (x, y, z) maps to Unity (x, z, y), the same mapping TiagoMocapFollower uses.
// This object is the rigid body's pivot (the centroid of its markers); the furniture model
// is a child placed at its measured offset (docs/LAB_MEASUREMENTS.md).
//
// Horizontal position shares TIAGo's mocap-to-Unity offset, so furniture and robot line up.
// Without a TIAGo (or before its first pose arrives) the first furniture pose anchors this
// object where it was placed in the editor. Height is always Motive's (floor at z = 0) plus
// floorHeight: TIAGo's follower sits on base_link, above the floor.
public class TrackedFurniture : MonoBehaviour
{
    [Header("ROS")]
    public string topicName = "/natnet_ros/table/pose";

    [Header("Frame")]
    [Tooltip("Share this follower's mocap-to-Unity offset. Leave empty to anchor on the first pose.")]
    public TiagoMocapFollower tiago;
    [Tooltip("Seconds to wait for TIAGo's first pose before anchoring on our own.")]
    public float tiagoWaitSeconds = 3f;
    [Tooltip("Scene Y of the real floor (Motive z = 0).")]
    public float floorHeight = 0f;

    [Header("Rotation")]
    [Tooltip("Keep only the heading; the furniture is level, so this hides marker jitter.")]
    public bool yawOnly = true;

    [Header("Smoothing")]
    public float smoothing = 10f;

    private ROSConnection ros;
    private Vector3 mappedPos;
    private Quaternion mappedRot;
    private bool havePose;
    private float firstPoseTime;

    private bool anchored;
    private Vector3 selfOffset;

    void Start()
    {
        ros = ROSConnection.GetOrCreateInstance();
        ros.Subscribe<PoseStampedMsg>(topicName, PoseCallback);
    }

    void PoseCallback(PoseStampedMsg msg)
    {
        var p = msg.pose.position;
        var q = msg.pose.orientation;
        mappedPos = new Vector3((float)p.x, (float)p.z, (float)p.y);
        // Mirror of the position mapping: swap y/z and flip handedness.
        mappedRot = Quaternion.Normalize(new Quaternion(-(float)q.x, -(float)q.z, -(float)q.y, (float)q.w));
        if (yawOnly)
        {
            var f = mappedRot * Vector3.forward;
            f.y = 0f;
            if (f.sqrMagnitude > 1e-6f)
                mappedRot = Quaternion.LookRotation(f, Vector3.up);
        }
        if (!havePose)
            firstPoseTime = Time.time;
        havePose = true;
    }

    void Update()
    {
        if (!havePose)
            return;

        Vector3 offset;
        if (tiago != null && tiago.isActiveAndEnabled && tiago.MocapInitialized)
        {
            offset = tiago.MocapPositionOffset;
        }
        else if (tiago != null && tiago.isActiveAndEnabled && Time.time - firstPoseTime < tiagoWaitSeconds)
        {
            return;
        }
        else
        {
            if (!anchored)
            {
                selfOffset = transform.position - mappedPos;
                anchored = true;
            }
            offset = selfOffset;
        }

        offset.y = floorHeight;
        var targetPos = mappedPos + offset;
        if (smoothing <= 0f)
        {
            transform.SetPositionAndRotation(targetPos, mappedRot);
        }
        else
        {
            float t = 1f - Mathf.Exp(-smoothing * Time.deltaTime);
            transform.SetPositionAndRotation(
                Vector3.Lerp(transform.position, targetPos, t),
                Quaternion.Slerp(transform.rotation, mappedRot, t));
        }
    }

    void OnDestroy()
    {
        if (ros != null)
            ros.Unsubscribe(topicName);
    }
}
