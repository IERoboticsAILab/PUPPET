using System;
using System.IO;
using UnityEngine;

namespace Puppet
{
    [Serializable]
    public class TopicRemap
    {
        public string from;
        public string to;
    }

    // Runtime settings, read from puppet_settings.json in the app's files folder:
    //   Quest: /sdcard/Android/data/<app id>/files/puppet_settings.json
    // The app writes a default file on first start. Edit it with unity/quest.sh (set-ip, pull, push)
    // or pick an address in the headset (left controller menu button), which also saves it here.
    [Serializable]
    public class PuppetSettings
    {
        public string robotIp = "";
        public int robotPort = 10000;
        public string[] ipPresets = { "10.205.3.26", "10.68.0.1" };
        // Changes topic and service names in the scene before anything subscribes or publishes,
        // e.g. {"from": "/mobile_base_controller/cmd_vel", "to": "/cmd_vel"}. Applies to public string
        // fields named like topicName, serviceName or ...Topic on every script in the scene.
        public TopicRemap[] topicRemaps = new TopicRemap[0];
        public bool showStatus = true;

        public const string FileName = "puppet_settings.json";
        public static string FilePath => Path.Combine(Application.persistentDataPath, FileName);

        public static PuppetSettings Load(out string problem)
        {
            problem = null;
            var path = FilePath;
            try
            {
                if (File.Exists(path))
                {
                    var s = JsonUtility.FromJson<PuppetSettings>(File.ReadAllText(path));
                    if (s != null)
                    {
                        s.ipPresets ??= new string[0];
                        s.topicRemaps ??= new TopicRemap[0];
                        return s;
                    }
                    problem = $"{FileName} is empty or not valid JSON; using defaults";
                }
            }
            catch (Exception e)
            {
                problem = $"Could not read {FileName}: {e.Message}; using defaults";
            }
            return new PuppetSettings();
        }

        public void Save()
        {
            try
            {
                File.WriteAllText(FilePath, JsonUtility.ToJson(this, true));
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[PUPPET] Could not save {FilePath}: {e.Message}");
            }
        }
    }
}
