using System;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

/// <summary>Минимальный логгер телеметрии для Unity: буфер → POST /events батчем.</summary>
public class TelemetryLogger : MonoBehaviour
{
    [Serializable] public class Ev { public string session_id, player_id, event_type, level; public double ts; public float x, y; }

    [SerializeField] private string serverUrl = "http://localhost:8000/events";
    [SerializeField] private int batchSize = 20;
    public string PlayerId = "p1";
    private readonly string _session = Guid.NewGuid().ToString("N");
    private readonly List<Ev> _buf = new();

    public void Log(string type, string level = null, Vector2? pos = null)
    {
        _buf.Add(new Ev { session_id = _session, player_id = PlayerId, event_type = type, level = level,
            ts = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0, x = pos?.x ?? 0, y = pos?.y ?? 0 });
        if (_buf.Count >= batchSize) Flush();
    }

    public void Flush()
    {
        if (_buf.Count == 0) return;
        var json = "[" + string.Join(",", _buf.ConvertAll(JsonUtility.ToJson)) + "]";
        _buf.Clear();
        StartCoroutine(Post(json));
    }

    private System.Collections.IEnumerator Post(string json)
    {
        using var req = new UnityWebRequest(serverUrl, "POST");
        req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json));
        req.downloadHandler = new DownloadHandlerBuffer();
        req.SetRequestHeader("Content-Type", "application/json");
        yield return req.SendWebRequest();
        if (req.result != UnityWebRequest.Result.Success) Debug.LogWarning(req.error);
    }

    private void OnApplicationQuit() => Flush();
}
