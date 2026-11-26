using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

// Runs MAIN PUPPET SCENE in Play mode from batch mode and records the in-headset status text
// (and a screenshot) at a few points in time. Used with a fake endpoint to check the status
// messages without a robot:
//
//   Unity -batchmode -projectPath . -executeMethod PuppetStatusPlayTest.Run \
//         -puppetTestOut /tmp/out -puppetTestIp 127.0.0.1 -puppetTestSeconds 14
//
// -puppetTestArm 1 also presses the extend-arm button through ArmCommander's own handlers
// (enable arm motion, then 'offer', then 'home' once the robot answers). Only against the
// mock robot (scripts/ros2/mock_robot.sh on ros2-port), never a real TIAGo.
//
// Writes <out>/status.txt and <out>/status_<t>.png, then exits. Leaves no changes in the project.
[InitializeOnLoad]
public static class PuppetStatusPlayTest
{
    const string Key = "PuppetStatusPlayTest.Out";
    static float[] SampleAt = { 1f, 3f, 6f, 9f, 12f };

    static string Arg(string name, string fallback)
    {
        var a = System.Environment.GetCommandLineArgs();
        int i = System.Array.IndexOf(a, name);
        return i >= 0 && i + 1 < a.Length ? a[i + 1] : fallback;
    }

    public static void Run()
    {
        var outDir = Arg("-puppetTestOut", "Logs/puppet_status_test");
        Directory.CreateDirectory(outDir);
        var settingsPath = Puppet.PuppetSettings.FilePath;
        var backup = settingsPath + ".testbackup";
        if (File.Exists(settingsPath)) File.Copy(settingsPath, backup, true);
        var s = new Puppet.PuppetSettings
        {
            robotIp = Arg("-puppetTestIp", "127.0.0.1"),
            robotPort = int.Parse(Arg("-puppetTestPort", "10000")),
        };
        s.Save();

        SessionState.SetString(Key, Path.GetFullPath(outDir));
        SessionState.SetFloat(Key + ".seconds", float.Parse(Arg("-puppetTestSeconds", "13")));
        SessionState.SetBool(Key + ".arm", Arg("-puppetTestArm", "0") == "1");
        EditorSceneManager.OpenScene("Assets/MAIN PUPPET SCENE.unity");
        EditorApplication.EnterPlaymode();
    }

    static PuppetStatusPlayTest()
    {
        if (string.IsNullOrEmpty(SessionState.GetString(Key, ""))) return;
        EditorApplication.update += Tick;
    }

    static int next;
    static float startedAt = -1f;
    static readonly StringBuilder log = new StringBuilder();

    static void Tick()
    {
        var outDir = SessionState.GetString(Key, "");
        if (string.IsNullOrEmpty(outDir) || !EditorApplication.isPlaying) return;
        if (startedAt < 0)
        {
            startedAt = Time.realtimeSinceStartup;
            float total = SessionState.GetFloat(Key + ".seconds", 13f);
            if (total > 13f)  // long runs: a sample every 3 s
                SampleAt = System.Linq.Enumerable.Range(0, (int)(total / 3f)).Select(i => 1f + 3f * i).ToArray();
        }
        float t = Time.realtimeSinceStartup - startedAt;
        if (SessionState.GetBool(Key + ".arm", false)) ArmTest(t);

        if (next < SampleAt.Length && t >= SampleAt[next])
        {
            float at = SampleAt[next];
            next++;
            try
            {
                // From 9 s on: the address picker and an arm-motion message, for the screenshots.
                if (at >= 9f && Arg("-puppetTestPicker", "0") == "1" && Puppet.PuppetStatus.Instance != null)
                {
                    Puppet.PuppetStatus.Instance.OpenAddressPickerForTests();
                    Puppet.PuppetStatus.ReportArm("Arm motion 'offer' got NO ANSWER from /tp_arm_motion/command. Arm teleop turned off; enable it again to retry.", true, 20f);
                }
                var st = Puppet.PuppetStatus.Instance;
                var text = st != null ? st.CurrentTextForTests : "(no PuppetStatus instance)";
                log.AppendLine($"--- t={at:F0}s ---").AppendLine(StripTags(text ?? "(null)"));
                Shot(Path.Combine(outDir, $"status_{at:F0}.png"));
            }
            catch (System.Exception e)
            {
                log.AppendLine($"--- t={at:F0}s --- sample failed: {e}");
            }
        }

        if (t >= SessionState.GetFloat(Key + ".seconds", 13f))
        {
            File.WriteAllText(Path.Combine(outDir, "status.txt"), log.ToString());
            SessionState.EraseString(Key);
            var settingsPath = Puppet.PuppetSettings.FilePath;
            var backup = settingsPath + ".testbackup";
            if (File.Exists(backup)) File.Copy(backup, settingsPath, true); else File.Delete(settingsPath);
            File.Delete(backup);
            EditorApplication.Exit(0);
        }
    }

    // ---- extend-arm button test (mock robot only) ----
    static int armStep;
    static ArmCommander arm;

    static void Press(string method)
    {
        var m = typeof(ArmCommander).GetMethod(method, System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        m.Invoke(arm, new object[] { default(UnityEngine.InputSystem.InputAction.CallbackContext) });
    }

    static void ArmTest(float t)
    {
        if (arm == null) arm = Object.FindObjectOfType<ArmCommander>();
        if (arm == null) return;
        switch (armStep)
        {
            case 0 when t >= 4f:
                Press("OnEnableMotion");
                Press("OnExtendArm");
                log.AppendLine($"[arm] t={t:F1}s enable + extend-arm button ('offer'), waiting={arm.WaitingForArmMotion}");
                armStep = 1;
                break;
            case 1 when !arm.WaitingForArmMotion:
                log.AppendLine($"[arm] t={t:F1}s reply: extended={arm.ArmExtended}, teleop={arm.MotionEnabled}");
                if (arm.ArmExtended)
                {
                    Press("OnExtendArm");
                    log.AppendLine($"[arm] t={t:F1}s extend-arm button again ('home'), waiting={arm.WaitingForArmMotion}");
                    armStep = 2;
                }
                else armStep = 3;
                break;
            case 2 when !arm.WaitingForArmMotion:
                log.AppendLine($"[arm] t={t:F1}s reply: extended={arm.ArmExtended}, teleop={arm.MotionEnabled}");
                armStep = 3;
                break;
        }
    }

    static string StripTags(string s) => System.Text.RegularExpressions.Regex.Replace(s, "<[^>]+>", "");

    static void Shot(string path)
    {
        var cam = Camera.main;
        if (cam == null) return;
        var rt = new RenderTexture(1280, 960, 24);
        var prev = cam.targetTexture;
        cam.targetTexture = rt;
        cam.Render();
        cam.targetTexture = prev;
        RenderTexture.active = rt;
        var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
        tex.Apply();
        RenderTexture.active = null;
        File.WriteAllBytes(path, tex.EncodeToPNG());
        Object.DestroyImmediate(tex);
        rt.Release();
    }
}
