#!/usr/bin/env bash
# Build PUPPET's ROS 2 workspace (ros2_ws) for TIAGo on PAL OS 25.01, inside PAL's development
# image, so the binaries match the robot exactly. Works on Linux amd64 and on macOS (Apple Silicon
# runs the amd64 image under emulation: slower, same result).
#
#   scripts/ros2/build.sh            build (and fetch dependencies the first time)
#   scripts/ros2/build.sh --test     build, then run the unit tests
#   scripts/ros2/build.sh --shell    open a shell in the build container
#   scripts/ros2/build.sh --image    only build PAL's image (first run: 10-30 min)
#
# Needs Docker and PAL's delivery script (uni-ie-build-docker.sh, with the client keys); set
# PAL_DOCKER_SCRIPT if it is not at ~/Downloads/uni-ie/uni-ie-build-docker.sh.
# The workspace is mounted at /home/pal/puppet_ws, the same path it has on TIAGo, so the install
# space can be copied to the robot as is (scripts/ros2/deploy.sh).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WS="$ROOT/ros2_ws"
ROBOT=${PAL_ROBOT:-tiago-38}
IMAGE="development-$ROBOT:alum-25.01"
PAL_DOCKER_SCRIPT=${PAL_DOCKER_SCRIPT:-$HOME/Downloads/uni-ie/uni-ie-build-docker.sh}
ROBOT_WS=/home/pal/puppet_ws

R=$'\e[31m'; G=$'\e[32m'; B=$'\e[1m'; N=$'\e[0m'
[[ -t 1 ]] || { R='' G='' B='' N=''; }
die() { echo "${R}error:${N} $*" >&2; exit 1; }
step() { echo "${B}==> $*${N}"; }

command -v docker >/dev/null || die "docker not installed (https://docs.docker.com/get-docker/)"
docker info >/dev/null 2>&1 || die "Docker is not running (macOS: open -a Docker)"

build_image() {
  [[ -f "$PAL_DOCKER_SCRIPT" ]] || die "PAL's script not found at $PAL_DOCKER_SCRIPT (set PAL_DOCKER_SCRIPT)"
  step "Building PAL's $IMAGE image (first time only; 10-30 min, longer under emulation)"
  # macOS ships bash 3.2, whose regex engine has no lazy '+?': PAL's script then picks a base
  # image that does not exist ("pull access denied ... deploy-alum-25.01-common"). '+' is
  # equivalent there (the captures are unused). PAL's script embeds client keys: never commit it.
  local patched; patched=$(mktemp)
  sed 's/+?)/+)/' "$PAL_DOCKER_SCRIPT" > "$patched"
  DOCKER_DEFAULT_PLATFORM=linux/amd64 bash "$patched" "$ROBOT" || { rm -f "$patched"; die "PAL image build failed (see above)"; }
  rm -f "$patched"
}

fetch_deps() {
  # dependencies/ros2.repos: name, url, version (pinned commit). Plain git, no vcstool needed.
  mkdir -p "$WS/src/deps"
  awk '/^  [A-Za-z0-9_-]+:$/ {n=$1; sub(":","",n)} /url:/ {u=$2} /version:/ {print n, u, $2}' "$ROOT/dependencies/ros2.repos" |
  while read -r name url version; do
    local dir="$WS/src/deps/$name"
    if [[ ! -d "$dir/.git" ]]; then
      step "Fetching $name"
      git clone -q "$url" "$dir"
    fi
    if [[ "$(git -C "$dir" rev-parse HEAD)" != "$version" ]]; then
      git -C "$dir" fetch -q origin "$version" 2>/dev/null || git -C "$dir" fetch -q origin
      git -C "$dir" checkout -q "$version"
    fi
  done
}

in_container() {  # in_container [-it] "<commands>"
  local tty=()
  if [[ "$1" == -it ]]; then tty=(-it); shift; fi
  docker run --rm ${tty[@]+"${tty[@]}"} --platform linux/amd64 --entrypoint bash \
    -v "$WS:$ROBOT_WS" -w "$ROBOT_WS" -e ROS_LOCALHOST_ONLY=1 \
    "$IMAGE" -c "source /opt/pal/alum/setup.bash && $1"
}

mode=${1:-build}
docker image inspect "$IMAGE" >/dev/null 2>&1 || build_image
[[ "$mode" == --image ]] && exit 0

fetch_deps

case "$mode" in
  --shell) in_container -it "exec bash" ;;
  build|--test)
    step "colcon build (in $IMAGE)"
    in_container "colcon build --merge-install --event-handlers console_cohesion+ --cmake-args -DCMAKE_BUILD_TYPE=Release" \
      || die "build failed (errors above)"
    if [[ "$mode" == --test ]]; then
      step "colcon test"
      in_container "colcon test --merge-install --event-handlers console_cohesion+ && colcon test-result --verbose" \
        || die "tests failed (above)"
    fi
    echo "${G}ok${N}  install space: ros2_ws/install  (copy to TIAGo: ./puppet deploy)"
    ;;
  *) die "unknown option $mode (see the top of this script)" ;;
esac
