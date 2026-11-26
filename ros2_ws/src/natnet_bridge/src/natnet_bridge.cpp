// OptiTrack Motive (NatNet) -> ROS 2: one geometry_msgs/PoseStamped topic per rigid body,
// /natnet_ros/<Motive rigid-body name>/pose (when the node is named natnet_ros), plus TF.
//
// The ROS 2 replacement for the rigid-body part of the vendored ROS 1 natnet_ros_cpp, which is
// all PUPPET uses. Same topic names, same frame (global_frame, default "world") and the same raw
// values: Motive's x, y, z, qx, qy, qz, qw are passed through untouched.
// Added: a warning when no frame arrives, and rigid bodies that appear after start-up are picked
// up (descriptions are re-read when an unknown ID shows up).

#include <atomic>
#include <chrono>
#include <cstring>
#include <map>
#include <memory>
#include <mutex>
#include <string>

#include <NatNetCAPI.h>
#include <NatNetClient.h>
#include <NatNetTypes.h>

#include <geometry_msgs/msg/pose_stamped.hpp>
#include <geometry_msgs/msg/transform_stamped.hpp>
#include <rclcpp/rclcpp.hpp>
#include <tf2_ros/transform_broadcaster.h>

class NatNetBridge : public rclcpp::Node
{
public:
  NatNetBridge() : Node("natnet_ros")
  {
    serverIp = declare_parameter<std::string>("server_ip", "10.205.3.3");
    clientIp = declare_parameter<std::string>("client_ip", "10.205.3.122");
    unicast = declare_parameter<std::string>("server_type", "unicast") == "unicast";
    multicastAddress = declare_parameter<std::string>("multicast_address", "239.255.42.99");
    commandPort = declare_parameter<int>("server_command_port", 1510);
    dataPort = declare_parameter<int>("server_data_port", 1511);
    globalFrame = declare_parameter<std::string>("global_frame", "world");
    publishTf = declare_parameter<bool>("publish_tf", true);
    tf = std::make_unique<tf2_ros::TransformBroadcaster>(*this);
  }

  ~NatNetBridge() override
  {
    client.SetFrameReceivedCallback(nullptr, nullptr);
    client.Disconnect();
  }

  bool connect()
  {
    unsigned char ver[4];
    NatNet_GetVersion(ver);
    RCLCPP_INFO(get_logger(), "NatNet SDK %d.%d.%d.%d, connecting to Motive at %s from %s (%s)",
                ver[0], ver[1], ver[2], ver[3], serverIp.c_str(), clientIp.c_str(), unicast ? "unicast" : "multicast");

    sNatNetClientConnectParams params;
    params.connectionType = unicast ? ConnectionType_Unicast : ConnectionType_Multicast;
    params.serverCommandPort = static_cast<uint16_t>(commandPort);
    params.serverDataPort = static_cast<uint16_t>(dataPort);
    params.serverAddress = serverIp.c_str();
    params.localAddress = clientIp.c_str();
    params.multicastAddress = unicast ? nullptr : multicastAddress.c_str();

    client.Disconnect();
    if (client.Connect(params) != ErrorCode_OK) {
      RCLCPP_ERROR(get_logger(), "Cannot connect to Motive at %s. Is Motive running there with streaming "
                   "on, and is client_ip %s an address of this machine?", serverIp.c_str(), clientIp.c_str());
      return false;
    }
    sServerDescription server;
    memset(&server, 0, sizeof(server));
    if (client.GetServerDescription(&server) != ErrorCode_OK || !server.HostPresent) {
      RCLCPP_ERROR(get_logger(), "Motive at %s does not answer (Streaming pane: Broadcast Frame Data on, "
                   "Transmission Type %s?)", serverIp.c_str(), unicast ? "Unicast" : "Multicast");
      return false;
    }
    RCLCPP_INFO(get_logger(), "Connected to %s %d.%d", server.szHostApp, server.HostAppVersion[0], server.HostAppVersion[1]);

    readDescriptions();
    client.SetFrameReceivedCallback(&NatNetBridge::onFrameStatic, this);
    watchdog = create_wall_timer(std::chrono::seconds(5), [this] {
      if (frames == 0) {
        RCLCPP_WARN(get_logger(), "No mocap frames from %s in the last 5 s (Motive paused or streaming off?)", serverIp.c_str());
      }
      frames = 0;
    });
    return true;
  }

private:
  void readDescriptions()
  {
    sDataDescriptions * defs = nullptr;
    if (client.GetDataDescriptionList(&defs) != ErrorCode_OK || !defs) {
      RCLCPP_WARN(get_logger(), "Could not read rigid-body descriptions from Motive");
      return;
    }
    std::lock_guard<std::mutex> lock(mutex);
    for (int i = 0; i < defs->nDataDescriptions; i++) {
      if (defs->arrDataDescriptions[i].type != Descriptor_RigidBody) {
        continue;
      }
      const auto * rb = defs->arrDataDescriptions[i].Data.RigidBodyDescription;
      if (bodies.count(rb->ID)) {
        continue;
      }
      const std::string name(rb->szName);
      RCLCPP_INFO(get_logger(), "Rigid body %d: %s -> ~/%s/pose", rb->ID, name.c_str(), name.c_str());
      bodies[rb->ID] = {name, create_publisher<geometry_msgs::msg::PoseStamped>("~/" + name + "/pose", 50)};
    }
    NatNet_FreeDescriptions(defs);
  }

  static void NATNET_CALLCONV onFrameStatic(sFrameOfMocapData * data, void * self)
  {
    static_cast<NatNetBridge *>(self)->onFrame(*data);
  }

  void onFrame(const sFrameOfMocapData & data)
  {
    frames++;
    const auto now = this->now();
    bool unknown = false;
    {
      std::lock_guard<std::mutex> lock(mutex);
      for (int i = 0; i < data.nRigidBodies; i++) {
        const auto & rb = data.RigidBodies[i];
        auto it = bodies.find(rb.ID);
        if (it == bodies.end()) {
          unknown = true;
          continue;
        }
        geometry_msgs::msg::PoseStamped msg;
        msg.header.stamp = now;
        msg.header.frame_id = globalFrame;
        msg.pose.position.x = rb.x;
        msg.pose.position.y = rb.y;
        msg.pose.position.z = rb.z;
        msg.pose.orientation.x = rb.qx;
        msg.pose.orientation.y = rb.qy;
        msg.pose.orientation.z = rb.qz;
        msg.pose.orientation.w = rb.qw;
        it->second.pub->publish(msg);

        if (publishTf) {
          geometry_msgs::msg::TransformStamped t;
          t.header = msg.header;
          t.child_frame_id = it->second.name;
          t.transform.translation.x = rb.x;
          t.transform.translation.y = rb.y;
          t.transform.translation.z = rb.z;
          t.transform.rotation = msg.pose.orientation;
          tf->sendTransform(t);
        }
      }
    }
    if (unknown && !rereading.exchange(true)) {
      // A rigid body was added in Motive after start-up. Not from the NatNet thread.
      rereadTimer = create_wall_timer(std::chrono::milliseconds(10), [this] {
        rereadTimer->cancel();
        readDescriptions();
        rereading = false;
      });
    }
  }

  struct Body
  {
    std::string name;
    rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr pub;
  };

  NatNetClient client;
  std::string serverIp, clientIp, multicastAddress, globalFrame;
  bool unicast {true}, publishTf {true};
  int commandPort {1510}, dataPort {1511};
  std::unique_ptr<tf2_ros::TransformBroadcaster> tf;
  std::map<int, Body> bodies;
  std::mutex mutex;
  std::atomic<int> frames {0};
  std::atomic<bool> rereading {false};
  rclcpp::TimerBase::SharedPtr watchdog, rereadTimer;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<NatNetBridge>();
  if (!node->connect()) {
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
