using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;
using TMPro;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Rendering;

namespace Puppet
{
    // Head-locked status text in the headset, plus robot address selection.
    // Created automatically when a scene loads, so no scene changes are needed.
    //
    // It shows: the ROS connection (unreachable, lost, wrong ROS 1 / ROS 2 app), data that stopped
    // arriving (joint states, camera, odometry, mocap, audio), arm-motion service state, and the
    // latest errors from the connector or the endpoint. When everything is fine it is one short line.
    //
    // Left controller menu button (F2 in the editor): open the robot address list, press again for
    // the next address, hold for one second to connect to the selected one. Nothing here moves the robot.
    [DefaultExecutionOrder(-1000)]
    public class PuppetStatus : MonoBehaviour
    {
#if ROS2
        public const string Protocol = "ROS 2";
        const string OtherApk = "PUPPET-ros1.apk";
#else
        public const string Protocol = "ROS 1";
        const string OtherApk = "PUPPET-ros2.apk";
#endif

        public static PuppetStatus Instance { get; private set; }

        enum Level { Ok, Info, Warn, Error }

        class Watch
        {
            public string prefix;
            public string label;
            public float staleAfter;
            public Level whenMissing;
            public string hint;
            public bool exact;
        }

        // First match wins. Topics a scene subscribes to but that match none of these get a generic entry.
        static readonly Watch[] Watches =
        {
            new Watch { prefix = "/joint_states", exact = true, label = "Robot joints", staleAfter = 1.5f, whenMissing = Level.Error,
                hint = "robot bringup or endpoint not publishing /joint_states" },
            new Watch { prefix = "/xtion/", label = "Camera", staleAfter = 3f, whenMissing = Level.Warn,
                hint = "camera driver off or topic renamed" },
            new Watch { prefix = "/head_front_camera/", label = "Camera", staleAfter = 3f, whenMissing = Level.Warn,
                hint = "camera driver off, compressed topic missing, or topic renamed" },
            new Watch { prefix = "/mobile_base_controller/odom", exact = true, label = "Base odometry", staleAfter = 3f, whenMissing = Level.Warn,
                hint = "mobile base controller not running" },
            new Watch { prefix = "/odom_mocap", exact = true, label = "Mocap", staleAfter = 2f, whenMissing = Level.Info,
                hint = "NatNet on archimedes not running or Motive not streaming" },
            new Watch { prefix = "/puck_mocap", exact = true, label = "Mocap", staleAfter = 2f, whenMissing = Level.Info, hint = "" },
            new Watch { prefix = "/natnet_ros/", label = "Mocap", staleAfter = 2f, whenMissing = Level.Info, hint = "" },
            // HeadSubscriber subscribes with the wrong type on ROS 1 and never gets data; not a fault.
            new Watch { prefix = "/head_controller/state", exact = true, label = "Head state", staleAfter = 0f, whenMissing = Level.Ok, hint = "" },
            new Watch { prefix = "/audio_", label = "Audio", staleAfter = 5f, whenMissing = Level.Info,
                hint = "audio is off unless TELEPRESENCE_AUDIO=true" },
        };

        PuppetSettings settings;
        string settingsProblem;
        ROSConnection ros;
        float connectStartedAt;
        string connectedTo = "";
        bool everConnected;
        float lastConnectedAt = -1f;

        // Written from any thread by the log hook.
        readonly object logLock = new object();
        string protocolMismatch;
        string versionMismatch;
        readonly List<(float time, string text)> recentErrors = new List<(float, string)>();
        readonly Queue<(LogType type, string text)> pendingLogs = new Queue<(LogType, string)>();

        // Arm-motion service state, reported by ArmCommander.
        string armLine;
        Level armLevel = Level.Ok;
        float armLineUntil = -1f;

        ArmCommander arm;
        TextMeshProUGUI text;
        RectTransform panel;
        Transform anchor;

        // Address picker.
        InputAction menuAction;
        bool pickerOpen;
        int pickerIndex;
        float pickerLastInput;
        float menuDownAt = -1f;
        bool menuHoldHandled;
        string pickerNotice;
        float pickerNoticeUntil;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            if (Instance != null) return;
            var go = new GameObject("PUPPET Status");
            DontDestroyOnLoad(go);
            go.AddComponent<PuppetStatus>();
        }

        // Runs after every scene object's Awake but before any Start, so the address and topic names
        // are in place before scripts register publishers and subscribers.
        void Awake()
        {
            Instance = this;
            Application.logMessageReceivedThreaded += OnLog;

            settings = PuppetSettings.Load(out settingsProblem);
            if (!System.IO.File.Exists(PuppetSettings.FilePath))
                settings.Save();

            ApplyTopicRemaps(BuiltInRemaps, settings.topicRemaps);

            ros = ROSConnection.GetOrCreateInstance();
            if (string.IsNullOrWhiteSpace(settings.robotIp))
                settings.robotIp = ros.RosIPAddress;
            if (settings.robotPort <= 0)
                settings.robotPort = ros.RosPort;
            ros.RosIPAddress = settings.robotIp.Trim();
            ros.RosPort = settings.robotPort;
            // The connector's own HUD is desktop-only (OnGUI) and invisible in the headset.
            ros.ShowHud = false;
            connectStartedAt = Time.realtimeSinceStartup;
            connectedTo = $"{ros.RosIPAddress}:{ros.RosPort}";
            Debug.Log($"[PUPPET] {Protocol} app, robot endpoint {connectedTo}, settings {PuppetSettings.FilePath}");

            menuAction = new InputAction("PUPPET address menu", InputActionType.Button);
            // Oculus XR plugin (used on the Quest build) calls it "start"; OpenXR calls it "menu".
            menuAction.AddBinding("<XRController>{LeftHand}/start");
            menuAction.AddBinding("<XRController>{LeftHand}/menu");
            menuAction.AddBinding("<XRController>{LeftHand}/menuButton");
            menuAction.AddBinding("<Keyboard>/f2");
            menuAction.Enable();
        }

        void OnDestroy()
        {
            Application.logMessageReceivedThreaded -= OnLog;
            menuAction?.Disable();
            menuAction?.Dispose();
            if (Instance == this) Instance = null;
        }

        // Names that differ on the robot software this app is built for. The scene keeps the ROS 1
        // names; these are applied first, then the settings file's topicRemaps. Contract with the
        // robot side: docs/ROS2_INTERFACE.md (branch ros2-port).
#if ROS2
        static readonly TopicRemap[] BuiltInRemaps =
        {
            // 25.01's mobile_base_controller (diff_drive) only takes TwistStamped; /key_vel is a
            // twist_mux input (priority 90), so PAL's joystick (100) still overrides the headset.
            new TopicRemap { from = "/mobile_base_controller/cmd_vel", to = "/key_vel" },
            // 25.01's Astra driver; ImageSubscriber adds /compressed.
            new TopicRemap { from = "/xtion/rgb/image_raw", to = "/head_front_camera/rgb/image_raw" },
        };
#else
        static readonly TopicRemap[] BuiltInRemaps = new TopicRemap[0];
#endif

        static Dictionary<string, string> RemapTable(TopicRemap[] builtIn, TopicRemap[] fromFile)
        {
            static IEnumerable<TopicRemap> Valid(TopicRemap[] r) =>
                (r ?? new TopicRemap[0]).Where(x => x != null && !string.IsNullOrEmpty(x.from) && !string.IsNullOrEmpty(x.to));
            var map = new Dictionary<string, string>();
            foreach (var r in Valid(builtIn)) map[r.from] = r.to;
            // A file entry may name either the scene's original name or the built-in new name.
            foreach (var r in Valid(fromFile))
            {
                var original = map.FirstOrDefault(kv => kv.Value == r.from).Key;
                map[original ?? r.from] = r.to;
            }
            return map;
        }

        static void ApplyTopicRemaps(TopicRemap[] builtIn, TopicRemap[] fromFile)
        {
            var map = RemapTable(builtIn, fromFile);
            if (map.Count == 0) return;
            foreach (var mb in FindObjectsOfType<MonoBehaviour>(true))
            {
                foreach (var f in mb.GetType().GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
                {
                    if (f.FieldType != typeof(string)) continue;
                    var n = f.Name.ToLowerInvariant();
                    if (!n.Contains("topic") && !n.Contains("service")) continue;
                    if (f.GetValue(mb) is string v && map.TryGetValue(v, out var to))
                    {
                        f.SetValue(mb, to);
                        Debug.Log($"[PUPPET] Remapped {mb.GetType().Name}.{f.Name}: {v} -> {to}");
                    }
                }
            }
        }

        void OnLog(string message, string stackTrace, LogType type)
        {
            if (type != LogType.Error && type != LogType.Exception && type != LogType.Assert) return;
            lock (logLock)
            {
                if (message.StartsWith("Incompatible protocol"))
                    protocolMismatch = message;
                else if (message.StartsWith("Incompatible ROS-TCP-Endpoint version") || message.StartsWith("Corrupted or unreadable ROS-TCP-Endpoint"))
                    versionMismatch = message;
                else
                    pendingLogs.Enqueue((type, message));
            }
        }

        // Called by ArmCommander.
        public static void ReportArm(string line, bool isError, float showForSeconds)
        {
            var s = Instance;
            if (s == null) return;
            s.armLine = line;
            s.armLevel = isError ? Level.Error : Level.Info;
            s.armLineUntil = showForSeconds > 0 ? Time.realtimeSinceStartup + showForSeconds : float.MaxValue;
        }

        public static void ClearArm()
        {
            if (Instance != null) Instance.armLine = null;
        }

        void Update()
        {
            DrainLogs();
            UpdatePicker();
            EnsureText();
            if (text == null) return;
            bool show = settings.showStatus || pickerOpen;
            if (anchor.gameObject.activeSelf != show) anchor.gameObject.SetActive(show);
            if (show) SetText(BuildText());
        }

        void DrainLogs()
        {
            lock (logLock)
            {
                while (pendingLogs.Count > 0)
                {
                    var (_, msg) = pendingLogs.Dequeue();
                    var line = msg.Split('\n')[0].Trim();
                    if (line.Length > 140) line = line.Substring(0, 140) + "...";
                    recentErrors.RemoveAll(e => e.text == line);
                    recentErrors.Add((Time.realtimeSinceStartup, line));
                }
                recentErrors.RemoveAll(e => Time.realtimeSinceStartup - e.time > 20f);
                while (recentErrors.Count > 3) recentErrors.RemoveAt(0);
            }
        }

        // ---- connection state ----

        enum Conn { Starting, Unreachable, Lost, Connected }

        Conn ConnectionState()
        {
            float now = Time.realtimeSinceStartup;
            if (!ros.HasConnectionThread) return everConnected ? Conn.Lost : Conn.Starting;
            // The connector raises its error flag at the start of each attempt and clears it on the
            // endpoint's handshake or any later message.
            if (ros.HasConnectionError)
                return everConnected ? Conn.Lost : (now - connectStartedAt < 1.5f ? Conn.Starting : Conn.Unreachable);
            if (now - connectStartedAt < 1.0f) return Conn.Starting;
            if (!everConnected) everConnected = true;
            lastConnectedAt = now;
            return Conn.Connected;
        }

        // ---- text ----

        static string Color(Level l) => l switch
        {
            Level.Ok => "#7CFC8A",
            Level.Info => "#B8C4D0",
            Level.Warn => "#FFD24A",
            _ => "#FF5C5C",
        };

        static string Line(Level l, string s) => $"<color={Color(l)}>{s}</color>";

        string BuildText()
        {
            float now = Time.realtimeSinceStartup;
            var sb = new StringBuilder();
            var problems = new List<(Level level, string text)>();
            var notes = new List<string>();

            string mismatch, version;
            List<string> errors;
            lock (logLock)
            {
                mismatch = protocolMismatch;
                version = versionMismatch;
                errors = recentErrors.Select(e => e.text).ToList();
            }

            var conn = ConnectionState();
            string head;
            if (mismatch != null)
            {
                var endpointProto = mismatch.Contains("using ROS2") ? "ROS 2" : mismatch.Contains("using ROS1") ? "ROS 1" : "the other ROS";
                head = Line(Level.Error, $"WRONG APP: the robot endpoint runs {endpointProto}, this app is {Protocol}.\nInstall {OtherApk} (see docs/QUEST_INSTALL.md).");
                problems.Add((Level.Error, ""));
            }
            else switch (conn)
            {
                case Conn.Starting:
                    head = Line(Level.Info, $"{Protocol}: connecting to {connectedTo} ...   (PUPPET {Application.version})");
                    break;
                case Conn.Unreachable:
                    head = Line(Level.Error, $"{Protocol}: cannot reach robot endpoint {connectedTo} (retrying)\n" +
                                             "Check: Quest and robot on the same WiFi, robot IP (menu button), endpoint running (./puppet up).");
                    problems.Add((Level.Error, ""));
                    break;
                case Conn.Lost:
                    head = Line(Level.Error, $"{Protocol}: connection to {connectedTo} LOST (retrying)\nRobot commands are not reaching the robot.");
                    problems.Add((Level.Error, ""));
                    break;
                default:
                    head = Line(Level.Ok, $"{Protocol}: connected to {connectedTo}");
                    break;
            }
            if (arm == null && Time.frameCount % 120 == 1) arm = FindObjectOfType<ArmCommander>();
            if (arm != null && arm.MotionEnabled)
                head += Line(Level.Warn, arm.ArmExtended ? "   ARM TELEOP ON" : "   arm enabled (arm at home)");
            if (version != null)
                problems.Add((Level.Warn, "Endpoint version mismatch: " + version));

            if (conn == Conn.Connected && mismatch == null)
                CheckTopics(now, problems, notes);

            if (armLine != null && now < armLineUntil)
                problems.Add((armLevel, armLine));

            if (settingsProblem != null)
                problems.Add((Level.Warn, settingsProblem));

            foreach (var e in errors)
                problems.Add((Level.Warn, "Error: " + e));

            sb.Append(head);
            foreach (var (level, t) in problems)
                if (!string.IsNullOrEmpty(t)) sb.Append('\n').Append(Line(level, t));
            if (notes.Count > 0)
                sb.Append('\n').Append(Line(Level.Info, string.Join("   ", notes)));

            if (pickerOpen) AppendPicker(sb);
            else if (pickerNotice != null && now < pickerNoticeUntil) sb.Append('\n').Append(Line(Level.Info, pickerNotice));
            return sb.ToString();
        }

        void CheckTopics(float now, List<(Level, string)> problems, List<string> notes)
        {
            // Data gets a few seconds after connecting before it counts as missing.
            bool grace = now - connectStartedAt < 4f;
            var seenLabels = new HashSet<string>();
            var infoMissing = new List<string>();

            foreach (var t in ros.AllTopics.ToArray())
            {
                if (!t.HasSubscriberCallback || t.IsService) continue;
                var w = Watches.FirstOrDefault(x => x.exact ? t.Topic == x.prefix : t.Topic.StartsWith(x.prefix))
                        ?? new Watch { label = t.Topic, staleAfter = 3f, whenMissing = Level.Warn, hint = "" };

                if (w.whenMissing == Level.Ok) continue;
                float last = t.LastMessageReceivedRealtime;
                bool never = last <= 0f;
                float age = now - last;
                if (!never && age <= w.staleAfter) continue;
                if (grace && never) continue;

                // Several mocap topics share one label; report each label once.
                string key = w.label + (w.whenMissing == Level.Info ? "" : t.Topic);
                if (!seenLabels.Add(key)) continue;

                if (w.whenMissing == Level.Info)
                {
                    infoMissing.Add($"{w.label.ToLowerInvariant()}: no data");
                    continue;
                }
                var when = never ? "never received" : $"none for {age:F0} s";
                var hint = string.IsNullOrEmpty(w.hint) ? "" : $" ({w.hint})";
                problems.Add((w.whenMissing, $"{w.label}: {t.Topic} {when}{hint}"));
            }
            notes.AddRange(infoMissing.Distinct());
        }

        // ---- robot address picker ----

        List<string> PickerChoices()
        {
            var list = new List<string>();
            void Add(string ip)
            {
                ip = ip?.Trim();
                if (!string.IsNullOrEmpty(ip) && !list.Contains(ip)) list.Add(ip);
            }
            Add(settings.robotIp);
            foreach (var p in settings.ipPresets) Add(p);
            return list;
        }

        void UpdatePicker()
        {
            float now = Time.realtimeSinceStartup;
            bool down = menuAction.IsPressed();

            if (down && menuDownAt < 0f)
            {
                menuDownAt = now;
                menuHoldHandled = false;
            }
            else if (down && !menuHoldHandled && pickerOpen && now - menuDownAt > 1.0f)
            {
                menuHoldHandled = true;
                ConnectToSelected();
            }
            else if (!down && menuDownAt >= 0f)
            {
                if (!menuHoldHandled)
                {
                    var choices = PickerChoices();
                    if (!pickerOpen)
                    {
                        pickerOpen = true;
                        pickerIndex = Math.Max(0, choices.IndexOf(settings.robotIp));
                    }
                    else if (choices.Count > 0)
                    {
                        pickerIndex = (pickerIndex + 1) % choices.Count;
                    }
                    pickerLastInput = now;
                }
                menuDownAt = -1f;
            }

            if (pickerOpen && !down && now - pickerLastInput > 12f)
            {
                pickerOpen = false;
                pickerNotice = "Robot address unchanged.";
                pickerNoticeUntil = now + 3f;
            }
        }

        void ConnectToSelected()
        {
            var choices = PickerChoices();
            pickerOpen = false;
            if (choices.Count == 0) return;
            var ip = choices[Mathf.Clamp(pickerIndex, 0, choices.Count - 1)];
            settings.robotIp = ip;
            settings.Save();
            Reconnect();
            pickerNotice = $"Robot address set to {ip}:{settings.robotPort} and saved.";
            pickerNoticeUntil = Time.realtimeSinceStartup + 5f;
        }

        void Reconnect()
        {
            ros.Disconnect();
            lock (logLock)
            {
                protocolMismatch = null;
                versionMismatch = null;
                recentErrors.Clear();
            }
            everConnected = false;
            connectStartedAt = Time.realtimeSinceStartup;
            connectedTo = $"{settings.robotIp}:{settings.robotPort}";
            ros.Connect(settings.robotIp, settings.robotPort);
            Debug.Log($"[PUPPET] Reconnecting to {connectedTo}");
        }

        void AppendPicker(StringBuilder sb)
        {
            var choices = PickerChoices();
            sb.Append("\n\n").Append(Line(Level.Ok, "ROBOT ADDRESS   (menu: next   hold menu 1 s: connect)"));
            sb.Append('\n').Append(Line(Level.Info, $"PUPPET {Application.version}, {Protocol}"));
            for (int i = 0; i < choices.Count; i++)
            {
                bool sel = i == pickerIndex;
                bool cur = choices[i] == settings.robotIp;
                var label = $"{(sel ? "> " : "   ")}{choices[i]}:{settings.robotPort}{(cur ? "   (current)" : "")}";
                sb.Append('\n').Append(sel ? Line(Level.Warn, label) : Line(Level.Info, label));
            }
            sb.Append('\n').Append(Line(Level.Info, "Add addresses in puppet_settings.json (unity/quest.sh set-ip)."));
        }

        // ---- head-locked text ----
        // A small world-space canvas parented to the camera: a dark panel sized to the text, drawn
        // over everything (ZTest Always) so the robot model or the lab never hides it. It uses only
        // UI/Default and TMP's SDF shader, which are always in the build.

        const float PixelsPerMeter = 1000f;
        const float MaxWidthPx = 1000f;
        const float PadX = 18f, PadY = 10f;
        string lastText;

        static Material OnTop(Material source)
        {
            var m = new Material(source);
            m.SetFloat("unity_GUIZTestMode", (float)CompareFunction.Always);
            m.renderQueue = 4000;
            return m;
        }

        void EnsureText()
        {
            var cam = Camera.main;
            if (cam == null) return;
            if (anchor != null && anchor.parent == cam.transform) return;

            if (anchor == null)
            {
                var root = new GameObject("PUPPET Status", typeof(RectTransform));
                var canvas = root.AddComponent<Canvas>();
                canvas.renderMode = RenderMode.WorldSpace;
                canvas.sortingOrder = 32000;
                anchor = root.transform;
                var rootRect = (RectTransform)anchor;
                rootRect.sizeDelta = new Vector2(MaxWidthPx + 2 * PadX, 1000f);
                rootRect.pivot = new Vector2(0.5f, 0f);

                var bg = new GameObject("Panel", typeof(RectTransform)).AddComponent<UnityEngine.UI.Image>();
                bg.color = new Color(0f, 0f, 0f, 0.9f);
                bg.material = OnTop(UnityEngine.UI.Graphic.defaultGraphicMaterial);
                bg.raycastTarget = false;
                panel = bg.rectTransform;
                panel.SetParent(anchor, false);
                panel.anchorMin = panel.anchorMax = new Vector2(0.5f, 0f);
                panel.pivot = new Vector2(0.5f, 0f);
                panel.anchoredPosition = Vector2.zero;

                text = new GameObject("Text", typeof(RectTransform)).AddComponent<TextMeshProUGUI>();
                text.rectTransform.SetParent(panel, false);
                text.rectTransform.anchorMin = Vector2.zero;
                text.rectTransform.anchorMax = Vector2.one;
                text.rectTransform.offsetMin = new Vector2(PadX, PadY);
                text.rectTransform.offsetMax = new Vector2(-PadX, -PadY);
                text.fontSize = 28f;
                text.alignment = TextAlignmentOptions.Center;
                text.enableWordWrapping = true;
                text.richText = true;
                text.raycastTarget = false;
                text.fontMaterial = OnTop(text.fontSharedMaterial);
            }
            anchor.SetParent(cam.transform, false);
            anchor.localPosition = new Vector3(0f, -0.42f, 1.2f);
            anchor.localRotation = Quaternion.identity;
            anchor.localScale = Vector3.one / PixelsPerMeter;
            foreach (var t in anchor.GetComponentsInChildren<Transform>(true))
                t.gameObject.layer = cam.gameObject.layer;
        }

        void SetText(string s)
        {
            if (s == lastText) return;
            lastText = s;
            text.text = s;
            var size = text.GetPreferredValues(s, MaxWidthPx, 0f);
            panel.sizeDelta = new Vector2(Mathf.Min(size.x, MaxWidthPx) + 2 * PadX, size.y + 2 * PadY);
        }

        // Used by Assets/Editor/PuppetStatusPlayTest.cs.
        public void OpenAddressPickerForTests()
        {
            pickerOpen = true;
            pickerIndex = 1;
            pickerLastInput = Time.realtimeSinceStartup;
        }

        public string CurrentTextForTests => text != null ? text.text : BuildText();
    }
}
