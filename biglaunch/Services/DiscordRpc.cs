using System;
using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace BigLaunch.Services;

/// <summary>
/// Discord Rich Presence over Discord's OWN local IPC pipe.
///
/// 🔴 Deliberately NOT the Discord Partner SDK (the 9.6 MB DLL Winhanced
/// ships): that is a gated, licensed component. The presence pipe is the free,
/// documented, public path — a named pipe at \\.\pipe\discord-ipc-N speaking
/// a 8-byte header (opcode, length) + JSON. No SDK, no NuGet, no binary.
///
/// Presence needs an Application ID from Discord's developer portal. There is
/// no legitimate way to invent one, so it is a setting: with none configured
/// the feature simply reports "not configured" instead of silently failing.
/// </summary>
public sealed class DiscordRpc : IDisposable
{
    private NamedPipeClientStream? _pipe;
    private readonly string _appId;
    private readonly int _pid = Environment.ProcessId;

    public bool Connected { get; private set; }
    public string Status { get; private set; } = "לא מחובר";

    public DiscordRpc(string appId) => _appId = appId ?? "";

    public async Task<bool> ConnectAsync()
    {
        if (string.IsNullOrWhiteSpace(_appId))
        {
            Status = "לא הוגדר מזהה אפליקציה";
            return false;
        }

        for (int i = 0; i < 10; i++)      // Discord numbers its pipes 0..9
        {
            try
            {
                var p = new NamedPipeClientStream(".", $"discord-ipc-{i}",
                                                  PipeDirection.InOut, PipeOptions.Asynchronous);
                await p.ConnectAsync(300).ConfigureAwait(false);

                _pipe = p;
                await SendAsync(0, JsonSerializer.Serialize(new { v = 1, client_id = _appId }))
                    .ConfigureAwait(false);
                Connected = true;
                Status = "מחובר";
                return true;
            }
            catch { /* try the next pipe index */ }
        }
        Status = "Discord לא פועל";
        return false;
    }

    public async Task SetActivityAsync(string details, string? state, DateTime? startedUtc)
    {
        if (!Connected || _pipe is null) return;
        try
        {
            var activity = new
            {
                details,
                state,
                timestamps = startedUtc is null
                    ? null
                    : new { start = new DateTimeOffset(startedUtc.Value, TimeSpan.Zero).ToUnixTimeSeconds() },
                assets = new { large_image = "biglaunch", large_text = "Big Launch" },
            };
            string payload = JsonSerializer.Serialize(new
            {
                cmd = "SET_ACTIVITY",
                nonce = Guid.NewGuid().ToString(),
                args = new { pid = _pid, activity },
            });
            await SendAsync(1, payload).ConfigureAwait(false);
        }
        catch
        {
            Connected = false;
            Status = "החיבור נותק";
        }
    }

    public async Task ClearAsync()
    {
        if (!Connected || _pipe is null) return;
        try
        {
            await SendAsync(1, JsonSerializer.Serialize(new
            {
                cmd = "SET_ACTIVITY",
                nonce = Guid.NewGuid().ToString(),
                args = new { pid = _pid, activity = (object?)null },
            })).ConfigureAwait(false);
        }
        catch { }
    }

    private async Task SendAsync(int opcode, string json)
    {
        if (_pipe is null) return;
        byte[] body = Encoding.UTF8.GetBytes(json);
        byte[] frame = new byte[8 + body.Length];
        BitConverter.GetBytes(opcode).CopyTo(frame, 0);
        BitConverter.GetBytes(body.Length).CopyTo(frame, 4);
        body.CopyTo(frame, 8);
        await _pipe.WriteAsync(frame).ConfigureAwait(false);
        await _pipe.FlushAsync().ConfigureAwait(false);
    }

    public void Dispose()
    {
        try { _pipe?.Dispose(); } catch { }
        Connected = false;
    }
}
