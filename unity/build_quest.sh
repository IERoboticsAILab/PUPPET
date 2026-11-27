#!/usr/bin/env bash
# Builds the Quest APKs: unity/PUPPET_Unity/Builds/PUPPET-ros2.apk and PUPPET-ros1.apk.
#
#   unity/build_quest.sh          # both (about 10-20 min each)
#   unity/build_quest.sh ros2     # one
#
# Close the project in the Unity Editor first; batch mode can't open a project that is open.
# URDF-Importer 0.5.2 marks its desktop assimp binaries "Any platform", so an Android build finds
# two assimp.dll and fails. They are only used by the editor's URDF import, so they are moved out of
# the package cache for the build and put back afterwards.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT="$REPO/unity/PUPPET_Unity"
UNITY="${UNITY:-/Applications/Unity/Hub/Editor/2022.3.62f2/Unity.app/Contents/MacOS/Unity}"
WHICH="${1:-all}"
case "$WHICH" in
  all) FLAVOURS="ros2 ros1" ;;
  ros1|ros2) FLAVOURS="$WHICH" ;;
  *) echo "usage: $0 [all|ros1|ros2]" >&2; exit 2 ;;
esac
RSP="$PROJECT/Assets/csc.rsp"
if [ -e "$RSP" ]; then
  echo "$RSP exists. This script manages that file; move it away first." >&2
  exit 1
fi
REV="$(git -C "$REPO" rev-parse --short HEAD)$(git -C "$REPO" diff --quiet HEAD -- unity || echo +)"

if [ -e "$PROJECT/Temp/UnityLockfile" ] && lsof "$PROJECT/Temp/UnityLockfile" >/dev/null 2>&1; then
  echo "The project is open in Unity. Close the editor and run this again." >&2
  exit 1
fi

NATIVE="$(ls -d "$PROJECT"/Library/PackageCache/com.unity.robotics.urdf-importer@*/Runtime/UnityMeshImporter/Plugins/AssimpNet/Native)"
PARKED="$(mktemp -d)"
restore() {
  for d in "$PARKED"/*; do [ -e "$d" ] && mv "$d" "$NATIVE/"; done
  rmdir "$PARKED"
}
trap restore EXIT
for d in win linux osx; do
  [ -e "$NATIVE/$d" ] && mv "$NATIVE/$d" "$NATIVE/$d.meta" "$PARKED/"
done

# Unity deletes tracked .meta files whose asset isn't on disk (some textures were never committed),
# and setting the app id flips a flag in ProjectSettings. Put both back after the build so the
# working tree only shows real changes.
DELETED_BEFORE="$(git -C "$REPO" ls-files --deleted -- unity/PUPPET_Unity)"
PS=unity/PUPPET_Unity/ProjectSettings/ProjectSettings.asset
PS_CLEAN=0; git -C "$REPO" diff --quiet -- "$PS" && PS_CLEAN=1
tidy() {
  rm -f "$RSP" "$RSP.meta"
  restore
  comm -13 <(echo "$DELETED_BEFORE" | sort) <(git -C "$REPO" ls-files --deleted -- unity/PUPPET_Unity | sort) \
    | grep '\.meta$' | (cd "$REPO" && tr '\n' '\0' | xargs -0 git checkout --) 2>/dev/null || true
  [ "$PS_CLEAN" = 1 ] && git -C "$REPO" checkout -- "$PS" || true
}
trap tidy EXIT

for f in $FLAVOURS; do
  LOG="$PROJECT/Logs/build_quest_$f.log"
  # ROS 2: compile editor and player scripts with the ROS2 define (see Assets/Editor/PuppetBuild.cs).
  if [ "$f" = ros2 ]; then echo "-define:ROS2" > "$RSP"; else rm -f "$RSP" "$RSP.meta"; fi
  METHOD=PuppetBuild.Build$(echo "$f" | sed 's/ros/Ros/')
  echo "Building $f (revision $REV), log: $LOG"
  "$UNITY" -batchmode -quit -projectPath "$PROJECT" -buildTarget Android \
    -executeMethod "$METHOD" -puppetRevision "$REV" -logFile "$LOG" || {
    echo "Build $f failed. Last errors from $LOG:" >&2
    grep -E "error CS|Error|Exception|PuppetBuild" "$LOG" | sort -u | tail -20 >&2
    exit 1
  }
  grep "\[PuppetBuild\]" "$LOG" || true

  # Check that the APK was compiled for the protocol its name says.
  apk="$PROJECT/Builds/PUPPET-$f.apk"
  # (grep -c, not -q: -q stops reading early, and pipefail then reports unzip's SIGPIPE.)
  marks="$(unzip -p "$apk" assets/bin/Data/Managed/Metadata/global-metadata.dat | LC_ALL=C grep -ao "Unity is in ROS[12] mode" | sort -u | tr '\n' ' ')"
  want="Unity is in $(echo "$f" | tr a-z A-Z) mode "
  [ "$marks" = "$want" ] || { echo "PUPPET-$f.apk protocol check failed (found: '${marks}'). Do not install it." >&2; exit 1; }
  echo "OK  $apk  ($(du -h "$apk" | cut -f1), $f)"
done
rm -f "$RSP" "$RSP.meta"
