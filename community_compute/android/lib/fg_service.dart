// Foreground service — keeps the app PROCESS alive so the main-isolate engine
// loop (and its local buffer) keeps contributing when the app is backgrounded,
// and shows a PERSISTENT notification with the live counters (translated in the
// last hour + rate/min) that updates in real time WITHOUT opening the app.
//
// Targets flutter_foreground_task v8.x. If a build fails here, adjust ONLY this
// file — the app is fully functional foreground-only without it.
import 'package:flutter_foreground_task/flutter_foreground_task.dart';

@pragma('vm:entry-point')
void ccStartCallback() {
  FlutterForegroundTask.setTaskHandler(_KeepAliveHandler());
}

class _KeepAliveHandler extends TaskHandler {
  @override
  Future<void> onStart(DateTime timestamp, TaskStarter starter) async {}
  @override
  void onRepeatEvent(DateTime timestamp) {}
  @override
  Future<void> onDestroy(DateTime timestamp) async {}
}

class FgService {
  static bool _inited = false;

  static Future<void> init() async {
    if (_inited) return;
    _inited = true;
    FlutterForegroundTask.initCommunicationPort();
    FlutterForegroundTask.init(
      androidNotificationOptions: AndroidNotificationOptions(
        channelId: 'cc_service',
        channelName: 'מחשוב קהילתי',
        channelImportance: NotificationChannelImportance.LOW,
        priority: NotificationPriority.LOW,
      ),
      iosNotificationOptions: const IOSNotificationOptions(),
      foregroundTaskOptions: ForegroundTaskOptions(
        eventAction: ForegroundTaskEventAction.repeat(60000),
        autoRunOnBoot: false,
        allowWakeLock: true,
        allowWifiLock: true,
      ),
    );
  }

  /// Ask for the notification permission (Android 13+) — the persistent status
  /// notification does NOT appear without it. Safe to call early at boot.
  static Future<void> requestPermissions() async {
    await init();
    try {
      final p = await FlutterForegroundTask.checkNotificationPermission();
      if (p != NotificationPermission.granted) {
        await FlutterForegroundTask.requestNotificationPermission();
      }
    } catch (_) {}
  }

  static Future<void> start() async {
    await init();
    await requestPermissions();
    if (await FlutterForegroundTask.isRunningService) return;
    await FlutterForegroundTask.startService(
      notificationTitle: 'מחשוב קהילתי פעיל',
      notificationText: 'מתחילים לתרום כוח-תרגום…',
      callback: ccStartCallback,
    );
  }

  static Future<void> stop() async {
    if (await FlutterForegroundTask.isRunningService) {
      await FlutterForegroundTask.stopService();
    }
  }

  /// Live counters into the persistent notification (called by the engine).
  static Future<void> updateStats({
    int lastHour = 0, double ratePerMin = 0, String stage = '', int total = 0,
    String uptime = '', bool paused = false}) async {
    try {
      if (!await FlutterForegroundTask.isRunningService) return;
      final title = paused ? 'מחשוב קהילתי - מושהה' : 'מחשוב קהילתי · $stage';
      final up = uptime.isEmpty ? '' : ' · פועל כבר $uptime';
      final text = paused
          ? 'המתג כבוי - הפעילו כדי להמשיך לתרום'
          : 'תורגמו $lastHour בשעה האחרונה · ${ratePerMin.toStringAsFixed(1)}/דקה$up';
      await FlutterForegroundTask.updateService(notificationTitle: title, notificationText: text);
    } catch (_) {}
  }

  // ---- battery optimization (so Android doesn't throttle the background loop)
  static Future<bool> isBatteryUnrestricted() async {
    try { return await FlutterForegroundTask.isIgnoringBatteryOptimizations; } catch (_) { return true; }
  }

  static Future<void> requestBatteryUnrestricted() async {
    try { await FlutterForegroundTask.requestIgnoreBatteryOptimization(); } catch (_) {}
  }
}
