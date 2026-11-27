# Offline stand-in for the lab: one image, used both as "TIAGo" (Gallium) and as "archimedes".
# Build context: this folder. python-is-python3: TIAGo's scripts start with #!/usr/bin/env python.
# The PUPPET checkout is mounted at /puppet at run time.
FROM ros:noetic-ros-base
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ros-noetic-controller-manager ros-noetic-joint-state-controller ros-noetic-joint-trajectory-controller \
      ros-noetic-position-controllers ros-noetic-kdl-parser ros-noetic-urdf ros-noetic-robot-state-publisher \
      ros-noetic-control-msgs ros-noetic-tf2-ros liborocos-kdl-dev python3-yaml \
      openssh-server openssh-client iproute2 iputils-ping tmux git python-is-python3 \
    && rm -rf /var/lib/apt/lists/*
# Pinned like dependencies/tiago_public_ws.rosinstall
RUN mkdir -p /deps && cd /deps \
    && git clone -q https://github.com/Unity-Technologies/ROS-TCP-Endpoint.git && git -C ROS-TCP-Endpoint checkout -q 993d366b8900bf9f3d2da444fde64c0379b4dc7c \
    && git clone -q https://github.com/pal-robotics/play_motion.git && git -C play_motion checkout -q 7d8e0b5fdbb214cf4371869dcbac7c121afd1b22
# TIAGo's environment: PAL's setup file and the deployed workspace, as ./puppet sources them.
RUN useradd -m -s /bin/bash pal && usermod -p '*' pal && mkdir -p /opt/pal/gallium /run/sshd \
    && echo 'source /opt/ros/noetic/setup.bash' > /opt/pal/gallium/setup.bash \
    && mkdir -p /home/pal/deployed_ws_tele && echo 'source /ws/devel/setup.bash' > /home/pal/deployed_ws_tele/setup.bash \
    && chown -R pal:pal /home/pal
