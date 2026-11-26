using RosMessageTypes.BuiltinInterfaces;
using RosMessageTypes.Std;

namespace Puppet
{
    // std_msgs/Header differs between ROS 1 (has seq, unsigned sec) and ROS 2 (no seq, signed sec).
    // The stamp is Unity's time since start, as before; the tp controllers don't use it.
    public static class RosHeader
    {
        public static HeaderMsg Make(double now, uint seq, string frameId)
        {
            var nanosec = (uint)((now % 1.0) * 1e9);
#if ROS2
            return new HeaderMsg(new TimeMsg((int)now, nanosec), frameId);
#else
            return new HeaderMsg(seq, new TimeMsg((uint)now, nanosec), frameId);
#endif
        }
    }
}
