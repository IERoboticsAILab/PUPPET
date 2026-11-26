#!/usr/bin/env bash
# Builds unity/PUPPET_Unity/Builds/PUPPET-dev.apk (app id com.ProjectX.pxspatialversion.dev) for Quest.
#
# URDF-Importer 0.5.2 marks its desktop assimp binaries "Any platform", so an Android build finds two
# assimp.dll and fails. They are only used by the editor's URDF import, so they are moved out of the
# package cache for the build and put back afterwards. Unity re-imports them the next time it opens.
#
#   hardware/lab_models/build_quest_dev.sh [log file]
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PROJECT="$REPO/unity/PUPPET_Unity"
UNITY="${UNITY:-/Applications/Unity/Hub/Editor/2022.3.62f2/Unity.app/Contents/MacOS/Unity}"
LOG="${1:-$PROJECT/Logs/build_quest_dev.log}"

NATIVE="$(ls -d "$PROJECT"/Library/PackageCache/com.unity.robotics.urdf-importer@*/Runtime/UnityMeshImporter/Plugins/AssimpNet/Native)"
PARKED="$(mktemp -d)"
restore() {
  for d in "$PARKED"/*; do [ -e "$d" ] && mv "$d" "$NATIVE/"; done
  rmdir "$PARKED"
}
trap restore EXIT
for d in win linux osx; do
  mv "$NATIVE/$d" "$NATIVE/$d.meta" "$PARKED/"
done

"$UNITY" -batchmode -quit -projectPath "$PROJECT" -buildTarget Android \
  -executeMethod LabFurnitureSetup.BuildQuestDev -logFile "$LOG"
echo "Built $PROJECT/Builds/PUPPET-dev.apk (log: $LOG)"
