// Fake TIAGo hardware: every joint goes exactly where it is commanded (position interfaces).
// Runs controller_manager at 100 Hz, like the real robot, so PAL's trajectory controllers and the
// telepresence controllers load, switch and command exactly as on TIAGo.
#include <controller_manager/controller_manager.h>
#include <hardware_interface/joint_command_interface.h>
#include <hardware_interface/joint_state_interface.h>
#include <hardware_interface/robot_hw.h>
#include <ros/ros.h>

class FakeHw : public hardware_interface::RobotHW
{
public:
  explicit FakeHw(ros::NodeHandle & nh)
  {
    nh.getParam("joints", names);
    std::map<std::string, double> initial;
    nh.getParam("initial", initial);
    pos.resize(names.size()); vel.assign(names.size(), 0.0); eff.assign(names.size(), 0.0); cmd.resize(names.size());
    for (size_t i = 0; i < names.size(); i++) {
      pos[i] = cmd[i] = initial.count(names[i]) ? initial[names[i]] : 0.0;
      js.registerHandle(hardware_interface::JointStateHandle(names[i], &pos[i], &vel[i], &eff[i]));
      pj.registerHandle(hardware_interface::JointHandle(js.getHandle(names[i]), &cmd[i]));
    }
    registerInterface(&js);
    registerInterface(&pj);
  }
  void write(double dt)
  {
    for (size_t i = 0; i < names.size(); i++) {
      vel[i] = dt > 0 ? (cmd[i] - pos[i]) / dt : 0.0;
      pos[i] = cmd[i];
    }
  }

private:
  std::vector<std::string> names;
  std::vector<double> pos, vel, eff, cmd;
  hardware_interface::JointStateInterface js;
  hardware_interface::PositionJointInterface pj;
};

int main(int argc, char ** argv)
{
  ros::init(argc, argv, "fake_hw");
  ros::NodeHandle nh, pnh("~");
  FakeHw hw(pnh);
  controller_manager::ControllerManager cm(&hw, nh);
  ros::AsyncSpinner spinner(2);
  spinner.start();
  ros::Rate rate(100);
  ros::Time last = ros::Time::now();
  while (ros::ok()) {
    const ros::Time now = ros::Time::now();
    const ros::Duration period = now - last;
    last = now;
    cm.update(now, period);
    hw.write(period.toSec());
    rate.sleep();
  }
}
