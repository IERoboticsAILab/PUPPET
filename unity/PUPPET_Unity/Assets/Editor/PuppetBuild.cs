using System;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

// Batch-mode Quest builds for ROS 1 and ROS 2. Run through unity/build_quest.sh, which also parks
// URDF-Importer's desktop assimp plugins (see hardware/lab_models/build_quest_dev.sh).
//
//   unity/build_quest.sh [all|ros1|ros2]   (calls PuppetBuild.BuildRos1 / BuildRos2)
//
// ROS-TCP-Connector picks ROS 1 or ROS 2 at compile time with the ROS2 scripting define, so each
// protocol is its own APK. The editor and the player must be compiled with the same define (the
// serialized layout of e.g. HeaderMsg differs), so build_quest.sh writes Assets/csc.rsp with
// -define:ROS2 for the ROS 2 build, starts Unity once per flavour, and removes the file after.
// The project's ROS Settings stay on ROS 1. Each APK has its own app id, so both can be installed
// side by side and Rodrigo picks one in the Quest app list.
public static class PuppetBuild
{
    const string ScenePath = "Assets/MAIN PUPPET SCENE.unity";

    struct Flavor
    {
        public string name, appId, productName, apk;
        public bool ros2;
    }

    static readonly Flavor Ros1 = new Flavor
    {
        name = "ros1", appId = "com.ProjectX.pxspatialversion.ros1", productName = "PUPPET ROS1",
        apk = "Builds/PUPPET-ros1.apk", ros2 = false,
    };

    static readonly Flavor Ros2 = new Flavor
    {
        name = "ros2", appId = "com.ProjectX.pxspatialversion.ros2", productName = "PUPPET ROS2",
        apk = "Builds/PUPPET-ros2.apk", ros2 = true,
    };

    public static void BuildRos1() => Run(Ros1);
    public static void BuildRos2() => Run(Ros2);


    static string Arg(string name)
    {
        var args = Environment.GetCommandLineArgs();
        int i = Array.IndexOf(args, name);
        return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
    }

    static void Run(Flavor f)
    {
        var group = BuildTargetGroup.Android;
        var oldId = PlayerSettings.GetApplicationIdentifier(group);
        var oldName = PlayerSettings.productName;
        var oldVersion = PlayerSettings.bundleVersion;
        var projectDefines = PlayerSettings.GetScriptingDefineSymbolsForGroup(group).Split(';');
        if (projectDefines.Contains("ROS2"))
            throw new Exception("Project settings already define ROS2 for Android. Remove it (Robotics > ROS Settings > Protocol ROS1); unity/build_quest.sh adds it per build.");

#if ROS2
        const bool compiledRos2 = true;
#else
        const bool compiledRos2 = false;
#endif
        if (compiledRos2 != f.ros2)
            throw new Exception($"Scripts are compiled for {(compiledRos2 ? "ROS 2" : "ROS 1")}, but this is the {f.name} build. Use unity/build_quest.sh.");

        var rev = Arg("-puppetRevision") ?? "dev";
        try
        {
            PlayerSettings.SetApplicationIdentifier(group, f.appId);
            PlayerSettings.productName = f.productName;
            PlayerSettings.bundleVersion = $"{f.name}-{rev}";
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { ScenePath },
                locationPathName = f.apk,
                target = BuildTarget.Android,
                targetGroup = group,
                options = BuildOptions.None,
            });
            var s = report.summary;
            Debug.Log($"[PuppetBuild] {f.name}: {s.result}: {f.apk} {s.totalSize / 1e6:F1} MB, {s.totalErrors} errors, {s.totalTime}");
            if (s.result != BuildResult.Succeeded)
                throw new Exception($"PuppetBuild {f.name} {s.result}");
        }
        finally
        {
            PlayerSettings.SetApplicationIdentifier(group, oldId);
            PlayerSettings.productName = oldName;
            PlayerSettings.bundleVersion = oldVersion;
            AssetDatabase.SaveAssets();
        }
    }
}
