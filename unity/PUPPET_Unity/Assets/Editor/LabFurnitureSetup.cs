using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

// Batch-mode helpers for swapping the lab table and shelf in MAIN PUPPET SCENE.
//   Unity -batchmode -quit -projectPath . -executeMethod LabFurnitureSetup.Report
//   Unity -batchmode -quit -projectPath . -executeMethod LabFurnitureSetup.Apply
//   hardware/lab_models/build_quest_dev.sh   (calls BuildQuestDev)
public static class LabFurnitureSetup
{
    const string ScenePath = "Assets/MAIN PUPPET SCENE.unity";
    const string TableModel = "Assets/LabModels/lab_table.fbx";
    const string ShelfModel = "Assets/LabModels/lab_shelf.fbx";
    const float FloorY = 0f;

    // Model offsets in the rigid body's frame (docs/LAB_MEASUREMENTS.md, "In Unity").
    static readonly Vector3 TableLocalPos = new Vector3(0.0072f, -0.7995f, -0.0030f);
    const float TableLocalYaw = -161.9f;
    static readonly Vector3 ShelfLocalPos = new Vector3(0f, -1.3657f, 0f);
    const float ShelfLocalYaw = -85.0f;

    // A separate app id so this build installs next to the lab's APK instead of over it.
    const string DevAppId = "com.ProjectX.pxspatialversion.dev";
    const string DevProductName = "PUPPET dev";
    const string ApkPath = "Builds/PUPPET-dev.apk";

    static string PathOf(Transform t) => t.parent == null ? t.name : PathOf(t.parent) + "/" + t.name;

    static Bounds WorldBounds(GameObject go)
    {
        var rs = go.GetComponentsInChildren<Renderer>(true);
        if (rs.Length == 0) return new Bounds(go.transform.position, Vector3.zero);
        var b = rs[0].bounds;
        foreach (var r in rs.Skip(1)) b.Encapsulate(r.bounds);
        return b;
    }

    // Outermost objects whose meshes come from an asset path containing `key`.
    static List<GameObject> OldFurniture(string key)
    {
        var roots = new HashSet<GameObject>();
        foreach (var mf in Object.FindObjectsOfType<MeshFilter>(true))
        {
            var p = mf.sharedMesh ? AssetDatabase.GetAssetPath(mf.sharedMesh) : "";
            if (!p.Contains(key) || p.StartsWith("Assets/LabModels/")) continue;
            roots.Add(PrefabUtility.GetOutermostPrefabInstanceRoot(mf.gameObject) ?? mf.gameObject);
        }
        return roots.OrderBy(g => PathOf(g.transform)).ToList();
    }

    public static void Report()
    {
        EditorSceneManager.OpenScene(ScenePath);
        var roots = OldFurniture("escritorio").Concat(OldFurniture("Shelf"));
        foreach (var go in roots)
        {
            var t = go.transform;
            var b = WorldBounds(go);
            Debug.Log($"[LabFurniture] FURNITURE '{PathOf(t)}' active={go.activeInHierarchy} pos={t.position:F3} rot={t.eulerAngles:F1} " +
                      $"scale={t.lossyScale:F3} bounds.min={b.min:F3} bounds.max={b.max:F3} src={AssetDatabase.GetAssetPath(PrefabUtility.GetCorrespondingObjectFromSource(go))}");
        }
        foreach (var c in Object.FindObjectsOfType<MonoBehaviour>(true))
        {
            var n = c.GetType().Name;
            if (n is "TiagoMocapFollower" or "PuckMocapFollower" or "ObjectOptiTrack" or "ROSConnection")
                Debug.Log($"[LabFurniture] {n} on '{PathOf(c.transform)}' pos={c.transform.position:F3} rot={c.transform.eulerAngles:F1}");
        }
    }

    // Replaces the generic desk and shelf with the measured, tracked models. Safe to re-run.
    public static void Apply()
    {
        var scene = EditorSceneManager.OpenScene(ScenePath);
        var tiago = Object.FindObjectsOfType<TiagoMocapFollower>(true)
            .FirstOrDefault(f => f.enabled && f.gameObject.activeInHierarchy);
        Debug.Log($"[LabFurniture] TIAGo follower: {(tiago ? PathOf(tiago.transform) : "none")}");

        Swap("escritorio", "Table (tracked)", TableModel, "/natnet_ros/table/pose", TableLocalPos, TableLocalYaw, tiago);
        Swap("Shelf", "Shelf (tracked)", ShelfModel, "/natnet_ros/shelf/pose", ShelfLocalPos, ShelfLocalYaw, tiago);

        EditorSceneManager.MarkSceneDirty(scene);
        if (!EditorSceneManager.SaveScene(scene))
            throw new System.Exception("Could not save " + ScenePath);
        Debug.Log("[LabFurniture] Saved " + ScenePath);
    }

    static void Swap(string oldKey, string name, string modelPath, string topic, Vector3 localPos, float localYaw,
                     TiagoMocapFollower tiago)
    {
        var old = OldFurniture(oldKey);
        if (old.Count == 0)
            throw new System.Exception($"No old furniture matching '{oldKey}'");

        // Bounds of the old pieces (re-enabled for a moment: disabled renderers have no bounds).
        foreach (var go in old) go.SetActive(true);
        var b = WorldBounds(old[0]);
        foreach (var go in old.Skip(1)) b.Encapsulate(WorldBounds(go));
        foreach (var go in old) go.SetActive(false);

        foreach (var existing in Object.FindObjectsOfType<TrackedFurniture>(true).Where(t => t.name == name).ToList())
            Object.DestroyImmediate(existing.gameObject);

        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(modelPath);
        if (prefab == null)
            throw new System.Exception("Missing " + modelPath);
        var model = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
        var size = WorldBounds(model).size;
        Debug.Log($"[LabFurniture] {modelPath} imported size={size:F3} (long side should be X)");

        var anchor = new GameObject(name);
        var tracked = anchor.AddComponent<TrackedFurniture>();
        tracked.topicName = topic;
        tracked.tiago = tiago;
        tracked.floorHeight = FloorY;

        model.transform.SetParent(anchor.transform, false);
        model.transform.localPosition = localPos;
        model.transform.localRotation = Quaternion.Euler(0f, localYaw, 0f);

        // Until mocap arrives, stand in the old piece's place: same centre, long side along its long side.
        float modelYaw = b.size.x >= b.size.z ? 0f : 90f;
        var rot = Quaternion.Euler(0f, modelYaw - localYaw, 0f);
        var target = new Vector3(b.center.x, FloorY, b.center.z);
        anchor.transform.SetPositionAndRotation(target - rot * localPos, rot);

        var nb = WorldBounds(model);
        Debug.Log($"[LabFurniture] {name}: replaced {string.Join(", ", old.Select(g => PathOf(g.transform)))} " +
                  $"(old bounds {b.min:F3}..{b.max:F3}); new bounds {nb.min:F3}..{nb.max:F3}; topic {topic}");
    }

    // Builds the main scene for Quest under a dev app id, then restores the project's id and name.
    // URDF-Importer 0.5.2 marks its desktop assimp binaries "Any platform", so Android gets two
    // assimp.dll and the build fails. hardware/lab_models/build_quest_dev.sh moves them out of the
    // (read-only) package cache for the build and back afterwards.
    public static void BuildQuestDev()
    {
        var group = BuildTargetGroup.Android;
        var oldId = PlayerSettings.GetApplicationIdentifier(group);
        var oldName = PlayerSettings.productName;
        try
        {
            PlayerSettings.SetApplicationIdentifier(group, DevAppId);
            PlayerSettings.productName = DevProductName;
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { ScenePath },
                locationPathName = ApkPath,
                target = BuildTarget.Android,
                targetGroup = group,
                options = BuildOptions.None,
            });
            var s = report.summary;
            Debug.Log($"[LabFurniture] Build {s.result}: {ApkPath} {s.totalSize / 1e6:F1} MB, {s.totalErrors} errors, {s.totalTime}");
            if (s.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
                throw new System.Exception("Build " + s.result);
        }
        finally
        {
            PlayerSettings.SetApplicationIdentifier(group, oldId);
            PlayerSettings.productName = oldName;
            AssetDatabase.SaveAssets();
        }
    }
}
