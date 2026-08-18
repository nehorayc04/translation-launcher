# Winhanced 0.9.9.3 — ניתוח הנדסי מלא ותוכנית שחזור

**נכתב כ:** ארכיטקט תוכנה בכיר / מהנדס מערכות Windows / Reverse Engineering
**מושא הניתוח:** `C:\Program Files\Winhanced` — Winhanced 0.9.9.3 Beta
**תאריך:** 2026-08-17
**אופי העבודה:** קריאה בלבד. שום קובץ של Winhanced לא שונה, לא הורץ ולא הוסר.

---

## 0. גבול האמינות — קִראו את זה לפני כל דבר אחר

זהו החלק החשוב ביותר במסמך, כי בלעדיו כל טענה כאן נשמעת ודאית יותר ממה שהיא.

### 0.1 התוכנה מוגנת במגן מסחרי עם הצפנת גופי-מתודות

פירקתי את `Winhanced.dll` (14.9MB) ואת 24 ה-DLL הנלווים באמצעות `ilspycmd` וקיבלתי **1,351 קבצי
`.cs`** ו-**4,656 טיפוסים** על פני **99 מרחבי-שמות**. אבל:

```csharp
// C:\tmp\whsrc\Winhanced.Services\PolicyConfigClient.cs — דוגמה מייצגת
[ComImport]
[Guid("870af99c-171d-4f9e-af0d-e63df40c2bc9")]
private class CPolicyConfigClient { }                    // ← מטא-דאטה אמיתי, שרד

[MethodImpl(MethodImplOptions.NoInlining)]
public static bool SetDefaultEndpoint(string deviceId)
{
    return true;                                          // ← גוף המתודה — סטאב. הלוגיקה מוצפנת.
}

static PolicyConfigClient()
{
    Xy9Ac91TTPsPd5mC4M.CIbUAhPuLA8nvrkWee.ExGYDduSGq();   // ← ה-bootstrap של המפענח
}
```

הסימנים, כולם מאומתים:
- **כל** גוף מתודה מתפרק ל-`return null;` / `return true;` / `{}`.
- `[MethodImpl(MethodImplOptions.NoInlining)]` על כל מתודה — מונע מה-JIT להטמיע ולחשוף קוד.
- מרחב-שמות bootstrap `Xy9Ac91TTPsPd5mC4M`, מחלקה `CIbUAhPuLA8nvrkWee`, מתודה `ExGYDduSGq()`
  נקראת מכל בנאי סטטי בתוכנה.
- **6 P/Invoke מעורפלים ל-`libclrjit`** — כלומר המגן מתחבר ל-JIT compiler עצמו ומפענח גוף-מתודה
  רגע לפני קומפילציה. זו טכניקת ה-JIT-hook הסטנדרטית של מגנים מסחריים.
- שדות פרטיים משמם מחדש לג'יבריש (`oB9L2eMx7nUhNjBF1fe`).

### 0.2 מה שרד ומה לא — הגבול המדויק

| ✅ שרד (מטא-דאטה) | ❌ לא שרד (מוצפן) |
|---|---|
| שמות טיפוסים, מרחבי-שמות, חברים + חתימות מלאות | **כל** גוף מתודה |
| ארגומנטים של תכונות: `DllImport("user32.dll")`, `[ComImport]`, `[Guid(...)]`, `[MarshalAs]` | **כל** מחרוזת שנמצאת בתוך מתודה |
| ערכי שדות `const` | נתיבי Registry, שאילתות WMI, כתובות URL, ארגומנטים ל-CLI |
| חברי `enum` (121 enums מלאים) | אתחולי `static readonly` |
| ירושה, מימוש ממשקים | סדר הפעולות בתוך כל פונקציה |

**המשמעות המעשית:** אני יכול לומר בוודאות *ש-Winhanced קוראת ל-`PowerSetActiveScheme`*, כי
ה-`DllImport` הוא מטא-דאטה. אני **לא** יכול לומר *לאיזה GUID* — כי זו מחרוזת בתוך מתודה.

### 0.3 איך בכל זאת שחזרתי את המנגנון

לא מהבינארי. מארבעה מקורות שקופים לחלוטין שהמגן לא נוגע בהם:

1. **113 קבצי XAML מקומפלים (`.xbf`)** — פוענחו עם `games/winhanced/work/xbf.py` של הפרויקט
   הזה (נבנה במקור ל-Track A) → **4,646 מחרוזות**: שמות טיפוסים, `x:Name`, שמות מאפיינים
   וטוקנים של מערכת-העיצוב.
2. **קבצי JSON וסקריפטים שנשלחים כטקסט גלוי** — `Config/smart-launch-watcher.json` וכו'.
3. **🔑 קבצי ה-runtime במחשב הזה** — `appsettings.json`, `wake-provision-state.json`,
   `desktop-display-baseline.json`, `oem-ownership.json`. אלה **הראיה הישירה למנגנון ה-Revert**.
4. **🔑 לוגים אמיתיים** — `whservice.log` (671KB), `watchdog.log`, `app_*.txt` (81KB).
   הלוגים מדפיסים את מה שהקוד עשה בפועל, כולל שמות ספקים, ערכים ותוצאות.

כל טענה מכאן ואילך מתויגת במקור שלה. אין ניחושים מוסווים כעובדות.

---

## 1. ארכיטקטורה, טכנולוגיה ואינטגרציה עם Windows

### 1.1 ה-stack — מאומת מ-`runtimeconfig.json` + `deps.json`

```json
{ "tfm": "net8.0",
  "frameworks": [ {"name":"Microsoft.NETCore.App","version":"8.0.0"},
                  {"name":"Microsoft.WindowsDesktop.App","version":"8.0.0"} ] }
```

| שכבה | הבחירה |
|---|---|
| Runtime | **.NET 8** (`net8.0`), framework-dependent |
| UI | **WinUI 3 / Windows App SDK 2.0.1** — XAML מקומפל ל-`.xbf` |
| חבילות | **217 חבילות NuGet**, 225 ספריות |
| זהות | **Sparse/MSIX Package** (`Packaging/SparsePackage`, `CustomCapability.SCCD`) |
| DB | **SQLCipher** (`SQLitePCLRaw.bundle_e_sqlcipher`) לנתוני משתמש + SQLite רגיל ל-seeds |

**Sparse Package זו החלטה ארכיטקטונית מרכזית:** האפליקציה מותקנת כ-Win32 רגילה תחת
`C:\Program Files` (גישה מלאה למערכת), אבל **רושמת זהות MSIX** — וכך מקבלת יכולות שמורות
ל-Store apps: Windows Toast Notifications אמיתיות, `AppInstance.FindOrRegisterForKey`
(single-instance מנוהל, נראה בלוג), ורישום כ-**Home App** של מערכת המשחקים של Windows.
`CustomCapability.SCCD` = Signed Custom Capability Descriptor — יכולת מותאמת שמחייבת חתימה
של Microsoft, מה שמסביר את הגישה ל-API-ים שמורים.

### 1.2 מודל ריבוי-התהליכים — מאומת מהלוגים

```
Winhanced.exe (apphost, WinUI 3, session user)
   │  IPC (named pipe)
   ├── WinhancedWatchdog  ──── supervisor + crash janitor, "Version: 1.0.0.7"
   │      └── whservice/WHService.exe  ← המנוע המורם (elevated engine)
   │      └── RTSS.exe (elevated)      ← האוברליי
   ├── WinhancedFseBridge.exe          ← גשר Fullscreen-Exclusive
   ├── WinhancedMaintenanceHost.exe    ← משימות תחזוקה
   └── RestartAgent.exe                ← הפעלה-מחדש עצמית
```

מלוג ה-watchdog האמיתי:
```
[2026-08-11 21:29:26] Winhanced Watchdog starting (engine supervisor + crash janitor)...
[2026-08-11 21:29:30] Started elevated RTSS from watchdog (PID 12884)
[2026-08-11 21:29:30] Started WHService engine (PID 13744) path='...whservice\WHService.exe'
[2026-08-16 08:00:38] Winhanced connected via IPC
[2026-08-16 08:03:06] App crashed or was killed; running system recovery...
[2026-08-16 08:03:06] No checkpoint available; nothing to recover.
```

**זו התשובה לשאלת ההרשאות.** האפליקציה עצמה **לא** רצה כ-Administrator. במקום זה:
- ה-Watchdog הוא supervisor קבוע שרץ מורם (הותקן פעם אחת בהתקנה).
- **הוא** מפעיל את `WHService.exe` המורם — שם מתבצעות כל פעולות המערכת הרגישות.
- האפליקציה מדברת עם המנוע דרך **named-pipe IPC** עם פרוטוקול מוגדר.

מה-`WatchdogMessageType` enum (37 סוגי הודעות, מטא-דאטה מאומת) ניתן לשחזר את כל חוזה ה-IPC:
`AppStarted`, `AppStopping`, `Heartbeat`, `EngineRestartRequest`, `SystemRecoveryRequest`,
`CheckpointCreate`, `CheckpointRestore`, `PowerOperation`, `OemOperation`, `LibraryOperation`,
`PrivilegedInstall`, `DisplayOperation`, `WakeSourceOperation` ועוד.

**זה בדיוק מודל ה-broker/least-privilege הנכון**, והוא מה שמונע את שתי הבעיות של אפליקציית
tweaks טיפוסית: לא צריך UAC בכל פעולה, ו-crash של ה-UI לא משאיר את המערכת במצב חצי-משונה
(ראו §4.2).

### 1.3 מלאי ה-P/Invoke — Windows API אמיתי (מטא-דאטה, מאומת)

הרשימה הזו **ודאית** כי `[DllImport("...")]` הוא ארגומנט של תכונה:

| DLL | מה זה מגלה |
|---|---|
| `user32` | `SetWinEventHook`, `SetWindowsHookEx`, `RegisterHotKey`, `RegisterRawInputDevices`, `SendInput`, `SetForegroundWindow`, `ShowWindow`, `SetWindowPos`, `EnumWindows`, `GetWindowThreadProcessId`, `AttachThreadInput` |
| `kernel32` | ניהול תהליכים, job objects, memory |
| `powrprof` | `PowerSetActiveScheme`, `PowerReadACValue`, `PowerWriteACValueIndex`, `PowerWriteDCValueIndex` |
| `ntdll` | קריאות מערכת נמוכות |
| `dxgi` / `d3d11` | ספירת מתאמים, מצב תצוגה |
| `advapi32` | Registry, שירותים, אבטחה |
| `setupapi` / `cfgmgr32` | ספירת התקנים, אפשור/נטרול (זו הדרך ל-wake devices) |
| `shell32` / `ole32` | ShellExecute, COM |
| `winmm` | טיימרים במולטימדיה |
| `libclrjit` ×6 | **המגן** — לא פונקציונליות |

**COM interfaces** (GUID-ים מאומתים): `IPolicyConfig` (`f8679f50-…`) + `CPolicyConfigClient`
(`870af99c-…`) — API **לא-מתועד** של Windows לקביעת התקן שמע ברירת-מחדל. שימוש ב-API לא מתועד
זו החלטה מודעת שמעידה על עומק ההשקעה.

### 1.4 שכבת החומרה — ספקים מרובים עם fallback

מלוג ה-`whservice.log` האמיתי, כל 15 שניות:

```
[dynamic-tdp-pressure] active=false renderer="" rendererGen=0
  gpu=0.0%  gpuValid=true  gpuSource="amd-adlx-direct"      gpuProviderGen=1  gpuFreshMs=1311
  cpu=25.0% cpuValid=true  cpuSource="windows-nt-per-core"  cpuProviderGen=1  cpuFreshMs=0
  maxCore=71.9% maxCoreValid=true maxCoreSource="windows-nt-per-core" maxCoreProviderGen=1
```

**🔑 זהו דפוס העיצוב החשוב ביותר שמצאתי בכל התוכנה.** כל קריאת חיישן נושאת ארבעה שדות מטא:

| שדה | תפקיד |
|---|---|
| `Source` | **מי** סיפק את המדידה (`amd-adlx-direct`, `windows-nt-per-core`) |
| `ProviderGen` | דור הספק — עולה כשהספק מוחלף/מאותחל מחדש |
| `FreshMs` | **גיל** הנתון במילישניות |
| `Valid` | האם המדידה תקפה בכלל |

זה מה שמאפשר לוגיקה כמו dynamic-TDP לרוץ בבטחה: אם `gpuValid=false` או `gpuFreshMs` גדול מדי,
הלוגיקה **לא פועלת על נתון ישן**. בלי זה, ספק חומרה שנתקע היה גורם לתוכנה להוריד TDP על סמך
מדידה בת דקה. **זה בדיוק המנגנון שמונע את מחלקת התקלות של "המערכת הגיבה לנתון מת".**

ספקי החומרה בפועל: RyzenAdj (AMD), ASUS WMI, **ADLX** (AMD GPU — נראה חי בלוג),
**Intel IGCL** (`ZD.IGCLWrapper`, `ZD.PlatformControl`), LibreHardwareMonitor,
**PawnIO** (דרייבר קרנל), RAMSPDToolkit, DiskInfoToolkit.

### 1.5 🔴 תיקון מהותי לדוח הקודם — סקריפטי RyzenAdj **אינם בשימוש**

הדוח `winhanced_servers_report.md` מציין ש-Winhanced "שולחת סקריפטים מוכנים-להרצה"
(`readjustService.ps1`, `readjust.py`, `pmtable-example.py`). **בדקתי — זה לא מדויק.**

הסקריפטים אכן קיימים ונקראים. אבל הם **קבצי-דוגמה מקוריים של פרויקט RyzenAdj** (upstream),
וכל התלויות שהם דורשים **חסרות**:

```
  MISSING  libryzenadj.dll
  MISSING  WinRing0x64.dll
  MISSING  WinRing0x64.sys
  MISSING  inpoutx64.dll
  MISSING  RyzenAdjServiceTask.xml.template
```

`installServiceTask.bat` בודק במפורש את חמשת הקבצים האלה ונכשל בלעדיהם. **מסקנה:** אלה קבצים
שנשלחים כחלק מהתלות ב-RyzenAdj (רישיון/ייחוס), לא נתיב-הרצה פעיל. הבקרה האמיתית על TDP עוברת
דרך `WHService.exe` המורם, לא דרך Scheduled Task של PowerShell.

**מה שכן קיים בתיקיית הדרייברים:** `Assets/Drivers/LICENSE-PawnIO.txt` בלבד — כלומר **PawnIO
מורד בזמן ההתקנה, לא נשלח**. מאומת מלוג ההתקנה:
```
[2026-07-26 22:30:43] PawnIO installation completed and verified
```

---

## 2. מיפוי תכונות, Revert ומנגנוני גיבוי

### 2.1 סכמת ההגדרות המלאה — 100 מאפיינים עם ערכים אמיתיים

שחזרתי את `AppSettings` פעמיים: את **הסכמה** ממטא-דאטה (`Winhanced.Models.Settings.AppSettings`,
בדיוק 100 מאפיינים ציבוריים), ואת **הערכים** מקובץ ה-runtime החי
`%LOCALAPPDATA%\Winhanced\appsettings.json`.

**קטגוריות עיקריות:**

| קטגוריה | מאפיינים |
|---|---|
| חשמל/TDP | `IsPowerPlanEnabled`, `CustomPowerPlanGuid`, `ControlTDP`, `TDPMode`, `minTDP:9`, `maxTDP:30`, `silentTDP:9`, `balancedTDP:15`, `performanceTDP:20`, `TDPValPl2` |
| תצוגה/FPS | `CurrentRefreshRate`, `SelectedRefreshRate:180`, `SelectedFPSTarget`, `SelectedFPSLimit`, `FrameLimitEqRefreshRate`, `CurrentResolution`, `AvailableRefreshRates`, `AvailableResolutions` |
| GPU (זוגות Supports/Enabled) | AFMF, RSR, ImageSharpening, AntiLag, Boost, CpuBoost, IntelFrameGeneration (+`ModesMask`), EnduranceGaming |
| אוברליי/FSE | `UseInAppOverlay`, `PerformanceOverlay:"off"`, `OverrideFSE:true`, `enableFseIntercept:true`, `enableFseDiagnostics` |
| קלט | `RemapGuideButton`, `AnalogStickMouseEnabled`, `AnalogStickMouseSensitivity`, `AnalogStickMouseDeadzone:6000` |
| עיצוב | `useAnimatedGameArt`, `backgroundBlurEnabled`, `specularHighlightsEnabled`, `showAppTileLabels`, `accentOverride`, `themePreference`, `HdrMode` |
| ספרייה/חנות | `storeWishlist`, `wishlistAlerts`, `calendarReminders`, `knownOtherGameDirectories`, `hiddenLibraryFilters`, `librarySortPreferences` |
| חדשות (7 דליים) | `whatsNewShowWinhanced/Steam/Deals/Giveaways/Wishlist/Releases`, `whatsNewBucketGaming/Entertainment/Podcasts` |
| Lossless Scaling | אובייקט מקונן עם 24 שדות — אינטגרציה עמוקה עם אפליקציה חיצונית |

**🔑 תבנית ה-`Supports*`/`Enabled*`** היא הליבה של ניהול התכונות: הזיהוי (`SupportsAFMF`)
מופרד מהבחירה (`EnabledAFMF`). כך תכונה שהחומרה לא תומכת בה **לא מוצגת** בכלל — לא מוצגת
ומושבתת, אלא נעדרת. זו הסיבה שהמסך נראה שונה לגמרי בין מכשירים.

### 2.2 🔑 מנגנון ה-Revert — הראיה הישירה

זו התשובה לשאלה "איך מתבצע Revert". מצאתי אותה **לא בקוד** (מוצפן) אלא בקבצי המצב על הדיסק.

**א. פנקס ביטול לפעולות התקנים** — `%LOCALAPPDATA%\Winhanced\wake-provision-state.json`:

```json
{
  "DisabledDevices": [
    "Intel(R) Wi-Fi 6E AX210 160MHz",
    "Realtek PCIe GbE Family Controller"
  ],
  "DisabledTaskWakes": []
}
```

**זה בדיוק מה שנכון לעשות.** התוכנה נטרלה יכולת wake בשני מתאמי רשת (כדי שהמחשב לא יתעורר
לבד), ו**רשמה בשמות המדויקים מה בדיוק היא שינתה**. ה-Revert אינו "החזר הכול לברירת מחדל" —
הוא "החזר בדיוק את שני אלה". התאמה מלאה ל-enum `PowerOperationKind` שכולל את
`ProvisionWakeTasks` ואת `RevertWakeTasks`.

**ב. קווי-בסיס (baselines)** — `C:\ProgramData\Winhanced\whservice\desktop-display-baseline.json`:

```json
{ "Version": 1, "Resolution": "1920x1080", "RefreshRate": 180,
  "ObservedUtc": "2026-08-11T18:29:50Z", "BootUtcTicks": 639220697181939726 }
```

לפני שינוי רזולוציה/רענון למשחק, המצב המקורי נשמר עם **חותמת אתחול**. `BootUtcTicks` הוא
הפרט המתוחכם: אם המחשב אותחל מאז, הבסיס הזה **לא רלוונטי** ואסור לשחזר ממנו. זה בדיוק אותו
עיקרון שהפרויקט הזה למד בכאב ב-[[game-update-makes-backups-stale]] — גיבוי חייב לדעת אם
העולם השתנה תחתיו.

קובץ מקביל: `oem-ownership.json` (`{"enabled": false, "updatedUtc": "..."}`) — מעקב אחרי
בעלות על הגדרות OEM, מקביל ל-`OemOperationKind.RestoreSuppressedState`.

**ג. Checkpoint לקריסה** — מלוג ה-watchdog:
```
[2026-08-16 08:03:06] App crashed or was killed; running system recovery...
[2026-08-16 08:03:06] No checkpoint available; nothing to recover.
```
תואם ל-enum `DriverFeatures { None, Checkpoint, Restore, HandleRestore, GpuTracking }`.
כלומר: לפני פעולה מסוכנת נוצר checkpoint; בקריסה ה-watchdog **משחזר אוטומטית**.

**ד. מסיר-התקנה ייעודי** — `C:\ProgramData\Winhanced\Uninstallers\<GUID>\WinhancedUninstaller.exe`.

**ה. גנרציה של סמכות-חומרה** — `hardware-authority.generation` = `639220697810692985`
(חותמת ticks). מונה-דורות שמאפשר לפסול מצב חומרה שנקבע לפני אתחול.

### 2.3 ❌ ממצא שלילי חשוב: אין System Restore ואין גיבוי Registry

חיפשתי במפורש ולא מצאתי: אין קריאה ל-`SRSetRestorePoint`, אין `srclient.dll` ברשימת
ה-P/Invoke, אין תיקיית גיבוי Registry, אין `.reg` שנשמר.

**זה ממצא לגיטימי ומשמעותי, לא כישלון חיפוש.** רשימת ה-P/Invoke היא מטא-דאטה מאומת — אם היה
`DllImport("srclient.dll")` הייתי רואה אותו.

**המסקנה הארכיטקטונית:** Winhanced בחרה במודל **"פנקס ביטול ממוקד"** במקום **"רשת ביטחון גורפת"**.
במקום נקודת שחזור שלמה לפני כל שינוי (איטי, כבד, לרוב מיותר), היא רושמת בדיוק מה שינתה ומחזירה
בדיוק את זה. זו החלטה נכונה לאפליקציה שמשנה עשרות ערכים קטנים ותכופים — אבל **היא מניחה
שהפנקס עצמו שלם**. אם `wake-provision-state.json` נמחק, שני המתאמים נשארים מנוטרלים לנצח בלי
שאיש יודע. (ראו §5 — ה-blueprint שלי מוסיף את השכבה החסרה הזו.)

### 2.4 מפת התכונות מלוג הריצה האמיתי

התיוג בלוג נותן את המערכת המלאה. 40 התגים הנפוצים ביותר:

| תג | מערכת |
|---|---|
| `[SqliteCache]` ×45 | שכבת מטמון DB |
| `[MainWindow]` ×39 | מעטפת ה-UI |
| `[Startup]` / `[StartupProfile]` | פרופיל אתחול עם מדידת זמן לכל שלב |
| `[MemWatch]` ×24 | ניטור זיכרון עצמי (§4.1) |
| `[SteamNews]`, `[NewsAggregator]`, `[GameDeals]`, `[Giveaways]`, `[WinhancedNews]` | צבירת תוכן |
| `[ProfileRuntime]` | פרופילים לכל משחק |
| `[BloomCanvas]`, `[WebPVisibility]`, `[WebPPresentation]` | שכבת רינדור (§3) |
| `[GPUManager]`, `[ADLXBinds]`, `[RSRFeature]` | בקרת GPU |
| `[FSE]` | Fullscreen Exclusive |
| `[InputFocusManager]`, `[InputManager]`, `[TouchKeyboard]` | קלט |
| `[SleepCoordinator]`, `[HibernateTimeout]`, `[DeepIdle]` | ניהול חשמל |
| `[GameEngineHost]`, `[GameSessionCoordinator]` | ניהול הפעלות משחק |
| `[LibraryWatcher]`, `[BackgroundImportProgress]` | סריקת ספרייה |
| `[BluetoothDiscovery]`, `[DeviceInfo]` | התקנים |
| `[EntitlementService]`, `[TokenRefreshService]`, `[TokenStore]` | חשבון/הרשאות |
| `[ThemeService]` | ערכת נושא |
| `[Watchdog]`, `[WinhancedUpdater]` | תשתית |

### 2.5 Smart Launch Watcher — הקונפיגורציה גלויה, הלוגיקה לא

`Config/smart-launch-watcher.json` (6,223 בתים) קריא לחלוטין:

```json
{ "enabled": true, "splashRestoreDebounceMs": 500,
  "monitoringIntervalMs": 1000, "maxMonitoringTimeMs": 90000,
  "signalSources": { "windowSweepIntervalMs": 500,
                     "processTreeIntervalMs": 1500,
                     "foregroundWindowIntervalMs": 250 },
  "blockerPatterns": [ /* 20 דפוסים */ ] }
```

כל דפוס: `name`, `category`, `blockerType`, `processNames`, `windowTitles`, `windowClasses`,
`priority`, `enabled`. חמישה מקורות-אות במקביל בתדרים שונים (חלון קדמי כל 250ms, סריקת חלונות
כל 500ms, עץ תהליכים כל 1.5s) עם תקרת זמן של 90 שניות.

**מבחינה משפטית:** ה-*צורה* של הקונפיגורציה גלויה וניתנת ללמידה. ה-*לוגיקה* שמחליטה מה לעשות
עם חלון שזוהה מוצפנת — ולפי המפה המשפטית של הפרויקט, אסור לשחזר אותה. הרעיון בלבד הוא בר-מימוש
עצמאי.

---

## 3. UI/UX, מערכת עיצוב ואפקטים

### 3.1 מערכת העיצוב המלאה — מ-`Resources/DesignSystem.xbf`

75 המחרוזות מהקובץ הזה הן **מערכת העיצוב המלאה**, במפורש:

**טיפוגרפיה**
- גופן: **Inter** (Light / Medium / SemiBold)
- סולם: `12, 14, 16, 18, 20, 22, 24`
- סגנונות: `H1TextStyle`, `H2TextStyle`, `H3TextStyle`, `Body1TextStyle`, `Body2TextStyle`, `SubtextStyle`
- אייקונים: **Segoe Fluent Icons** (+ `Segoe MDL2 Assets` כ-fallback)

**מרווחים (סולם 4-בסיס)**
`SpacingXXSmall(2)`, `SpacingXSmall(6)`, `SpacingSmall(12)`, `SpacingMedium(20)`, `SpacingOffsetCenter`

**רדיוסים — היררכיה מלאה**
`CornerRadiusSmall`, `CornerRadiusMedium`, `CornerRadiusLarge`, `GlassPillCornerRadius`,
`GameCardCornerRadius` + `GameCardGlowCornerRadius`, `FilterCardCornerRadius` + `…GlowCornerRadius`,
`DiscordCardCornerRadius` + `…GlowCornerRadius`

**🔑 שימו לב לתבנית:** לכל סוג כרטיס יש **שני** רדיוסים — אחד למשטח ואחד לזוהר. הזוהר גדול
יותר במעט, כך שהוא "יוצא" מהכרטיס בצורה נכונה ולא נחתך. זה סוג הפרט שמפריד בין ממשק שנראה
מקצועי לאחד שנראה חובבני.

**חומרים — שכבת ה"Living Glass"**
```
AcrylicBrush           ← TintColor, TintOpacity, TintLuminosityOpacity, AlwaysUseFallback
GlassOnlyAcrylicBrush / GlassOnlyAcrylicBrushBG
GameDetailsGlassAcrylicBrush
BladeSurfaceAcrylicBrush
StoreTileGlassFlatBrush
GlassButtonBrush / GlassButtonStyle
GlassPillPowerButtonStyle / GlassPillBorderBrush
GlowDiffusionBrush
```

**🔑 `AlwaysUseFallback` הוא הפרט הקריטי.** זהו מאפיין של `AcrylicBrush` ב-WinUI שמאלץ מעבר
למשטח אטום כשהאקריליק לא זמין (חומרה חלשה, RDP, חיסכון בסוללה, `prefers-reduced-transparency`).
Winhanced מגדירה אותו במפורש — כלומר **תוכננה במפורש** לדרדור חינני, ולא נשענת על התנהגות
ברירת המחדל.

**מצבי בהירות** — לכל צבע יש זוג:
`CardSurfaceLightBrush` / `CardSurfaceDarkBrush`, `NavHeaderBrushLight` / `NavHeaderBrushDark`,
`CardFocusGlowBrushLight` / `CardFocusGlowBrushDark`

**מיקוד (focus) — עיצוב ייעודי לבקר**
`CardFocusGlowBrush{Light,Dark}`, `CardFocusGlowBorderThickness`, `CardEdgeBorderThickness`

זו החלטה משמעותית: הפריט הממוקד מקבל **זוהר**, לא רק מסגרת. בממשק 10-רגל שמנווטים בו בג'ויסטיק,
מסגרת דקה לא נראית מהספה — זוהר כן.

**רכיבים מורכבים — משפחת ה-SmartChip**
```
SmartChipStyle · SmartChipIconStyle · SmartChipTextStyle · SmartChipTextLargeStyle
SmartChipAccentStyle · SmartChipAccentIconStyle · SmartChipAccentTextStyle
PrimaryCTAButtonStyle · StatusIndicatorIconStyle · StatusIndicatorButtonStyle
```

**צבע מערכת:** `SystemAccentColor` + `LayerOnAccentAcrylicFillColorDefault` — כלומר צבע ההדגשה
נגזר מהגדרת Windows של המשתמש, לא מקובע.

### 3.2 מנוע הרינדור — הרבה מעבר ל-XAML רגיל

מ-`deps.json` ומהלוגים:

| טכנולוגיה | תפקיד |
|---|---|
| **ComputeSharp.D2D1** | שיידרים ב-HLSL שנכתבים ב-C# |
| `DynamicRimShader`, `MinimalRimShader`, `PassThroughShader` | שיידרים בפועל — "rim lighting" על כרטיסים |
| **Win2D** | ציור דו-ממדי מואץ |
| **Lottie** (`CommunityToolkit.WinUI.Lottie` + `LottieGen.MsBuild`) | אנימציות וקטוריות מקומפלות |
| **WebP מונפש** | אומנות משחקים חיה (`[WebPVisibility]`, `[WebPPresentation]`) |
| `[BloomCanvas]` | שכבת bloom/זוהר ייעודית |

`specularHighlightsEnabled` ב-appsettings + `DynamicRimShader` = **הבהק על שולי הכרטיסים נע עם
המיקוד**. זה ה-"Living Glass". `borderColors=10` ו-`rimTiles=19` בלוג ה-MemWatch מראים שזה
מנוהל כמאגר (pool) ולא נוצר מחדש לכל כרטיס.

### 3.3 ניהול משאבי רינדור — `DeepIdle`

מהלוג האמיתי:
```
[DeepIdle] ENTER gen=1 reasons=WindowInactive webp=4  applyMs=10.06
[DeepIdle] EXIT  gen=2 webp=14 idleMs=768  applyMs=3.81
[DeepIdle] ENTER gen=3 reasons=WindowInactive webp=14 applyMs=0.86
```

כשהחלון מאבד מיקוד, התוכנה נכנסת ל-DeepIdle: **מקפיאה את כל נגני ה-WebP** (`webp=14`), עם
מונה-דורות (`gen`) ומדידת זמן החלה (`applyMs`). היציאה מדווחת כמה זמן היה במצב סרק.

**זה בדיוק מה שהפרויקט הזה למד ב-[[qtwebengine-ui-gotchas]]**: אנימציה רציפה מאחורי חלון לא-פעיל
היא רצח FPS. Winhanced פותרת את זה במפורש ומודדת את העלות של הפתרון עצמו.

### 3.4 מבנה הניווט — מ-`MainWindow.xbf`

(פוענח בסבב קודם, מובא כאן להשלמה)
- `BumperPillNavigation` — LB ‹ גלולות › RB, עם `GlowUnderline` על הלשונית הפעילה
- `PinnedSecondaryNavHost` — LT ‹ צ'יפים › מיון ▾ + מונה-טווח › RT
- `GlassRailHost` / `HomeGameInfoPanel` לצד `RecentGames` (ItemsRepeater אופקי)
- `NavFooterGrid` — שורת רמזי הבקר
- `BackgroundImageA/B` (הצלבה) + `BloomCanvas` + `AcrylicVeil`
- כרטיס: `ShadowHost > FocusableCardButton > CardChrome + TintOverlay + CardSpecularRim +
  BoxArtImage + GlassSourceBadge + FocusGlowBorder + FocusScaleTransform`
- מצבי מיקוד: `Unfocused` / `Focused` / `PointerFocused`

**`PointerFocused` כמצב שלישי** הוא פרט חשוב: עכבר ובקר מקבלים מצב ויזואלי שונה, כי ההקשר שונה.

### 3.5 נגישות

מהלוג:
```
[ThemeService] UISettings wired ✓
[ThemeService] AccessibilitySettings is unavailable in this app context;
               Windows high-contrast fallback active (HighContrast=False)
```

התוכנה מנסה `AccessibilitySettings` (WinRT), ובהקשר Win32-עם-זהות-דלילה זה לא זמין — אז היא
**נופלת חזרה לזיהוי ניגודיות-גבוהה של Windows** ומדווחת על כך. `AlwaysUseFallback` על האקריליק
משלים את התמונה.

---

## 4. ביצועים, בטיחות ותחזוקה

### 4.1 ניטור עצמי — `MemWatch`

כל 5 שניות, לתוך הלוג:
```
[MemWatch] workingSet=527MB (Δ+0MB/5s) private=540MB gcHeap=24MB gcCommitted=70MB
           gen2=7 handles=4183 threads=119 | webpCtrls=14 players=1/0loaded
           pools=0 poolMB=0 uploadMB=0(+0/5s) uploadOps=0 frames=+7 draws=+0
           | rimTiles=19 boxArtLru=0 borderColors=10
```

**זו טלמטריה של מהנדס, לא של מוצר.** היא עוקבת אחרי working set + דלתא, זיכרון פרטי, ערמת GC,
**אוספי gen2** (המדד האמיתי ללחץ זיכרון ב-.NET), ידיות, תהליכונים — ובנוסף אחרי משאבי ה-UI
עצמם: כמה בקרי WebP, כמה מהם טעונים, גודל מאגרי הטקסטורות, בתי-העלאה ל-GPU, ספירת פריימים
וציורים, ומטמון ה-LRU של אומנות התיבה.

זה מאפשר לענות על "מי אכל את הזיכרון" בלי דיבאגר.

### 4.2 בטיחות — למה קריסה לא הורסת את המערכת

ארבע שכבות, כולן מאומתות:

1. **הפרדת הרשאות** — ה-UI לא מורם; פעולות רגישות עוברות ל-`WHService.exe` המורם דרך IPC
   מוגדר. קריסת UI לא משאירה פעולה חצי-מבוצעת.
2. **Supervisor קבוע** — ה-watchdog חי גם כשהאפליקציה סגורה, ומזהה קריסה:
   `App crashed or was killed; running system recovery...`
3. **Checkpoint/Restore** — `DriverFeatures {Checkpoint, Restore, HandleRestore}`; בקריסה מנסה
   לשחזר. אם אין checkpoint, אומר זאת במפורש ולא מנחש.
4. **קווי-בסיס עם חותמת-אתחול** — גיבוי שיודע לפסול את עצמו אם המערכת אותחלה.

בנוסף: `WHService crash dump policy: disabled for release build` — מדיניות dump מפורשת לפי
סוג הבנייה.

### 4.3 חסימת תכונות לפי גרסת Windows — מאומת

```
[System] Windows: 25H2 (Build 26200.8973) | Edition: Professional
[FSE] Windows version: 10.0.26200.0 (Build 26200.0)
[FSE] Required: Windows 11 build 26100.7019+ for native FSE API
[FSE] Gaming FSE API (api-ms-win-gaming-experience-l1-1-0) available: True
[FSE] Successfully registered for FSE state change notifications
```

**זו בדיקה ראויה לחיקוי:** לא רק *מספר גרסה* אלא **בדיקת זמינות של ה-API בפועל**
(`api-ms-win-gaming-experience-l1-1-0`). מספר בנייה יכול לשקר (Insider, backport); זמינות
ה-API לא. שתי הבדיקות יחד.

זיהוי חומרה מקביל, ונכשל בחן:
```
[DeviceManager] MSI built-in recovery probe: VID_0DB0 HID interfaces=0, XInput controllers=0
[DeviceManager] MSI built-in recovery: no VID_0DB0 HID on the bus — cannot re-enable via HID
[GPUManager] CreateGPU: 'AMD Radeon RX 9070' ven=0x1002 dev=0x7550
```

### 4.4 ניהול משאבים דינמי

```
[SystemMemory] System Memory: 32688MB total, 13105MB available (59% in use),
               Budget for suspended: 18352MB, Recommended max games: 3
[GameSessionCoordinator] Dynamic limits: MaxGames=3, MaxMemory=18352MB
```

מספר המשחקים שניתן להשהות במקביל (Quick Resume) **מחושב מהזיכרון הפנוי בפועל**, לא מקובע.

### 4.5 פרופיל אתחול

```
[StartupProfile] App ctor ENTER — 2435ms since process start (OS+runtime+WinAppSDK load)
[StartupProfile] App.xaml InitializeComponent took 14ms
[StartupProfile] ConfigureServices took 44ms
[StartupProfile] OnLaunched waited 0ms for startup tracks
```

**2,435ms** מהפעלת התהליך עד לבנאי — זו העלות של .NET 8 + WinAppSDK, וזו הסיבה למסך פתיחה.
הקוד של האפליקציה עצמו עולה 58ms בלבד. המדידה מפרידה במפורש בין "מה שאני שולט בו" לבין
"מה שאני משלם ל-runtime" — כך יודעים איפה בכלל אפשר לשפר.

### 4.6 שכבת החשבון

```
[EntitlementService] Loaded cached entitlement: tier=public, source=none, earlyAccess=False
[EntitlementService] Scheduling background refresh: cache expired
[EntitlementService] No API session found - using public tier
```

`entitlementsettings.json` נושא `CacheExpiration` של **2 דקות** — רענון תכוף עם דרגה ציבורית
כברירת מחדל. השרת: `https://api.winhanced.com` (הקבוע היחיד ששרד את ההצפנה).

---

## 5. תוכנית שחזור — Replication Blueprint

### 5.1 ה-stack המומלץ

| רכיב | המלצה | נימוק |
|---|---|---|
| Runtime | **.NET 8/9** | אותה בחירה של Winhanced, ומהסיבה הנכונה: זה ה-runtime היחיד עם P/Invoke ראשון-במעלה + WinRT + אקוסיסטם NuGet |
| UI | **WinUI 3 + Windows App SDK** | Mica/Acrylic מקוריים, Fluent, תמיכת בקר. **לא Electron** (זיכרון), **לא WPF** (חומרים ישנים) |
| זהות | **Sparse Package** | Win32 מלא + התראות/יכולות MSIX |
| DB | **SQLite + EF Core**; SQLCipher רק לנתונים אישיים | הצפנת מטמון ציבורי היא עלות בלי תמורה |
| חומרה | **LibreHardwareMonitor** (MPL-2.0) | קריאה בלבד; להימנע מדרייבר קרנל אלא אם חובה |
| אוברליי | **RTSS** דרך `RTSSSharedMemoryNET` | אין הזרקה עצמית |

**מה לא לשחזר:** אין צורך במגן JIT. הוא עלה ל-Winhanced ביכולת דיבאג, בזמן אתחול, ובאמון —
ולא מנע מסמך כמו זה.

### 5.2 ארכיטקטורת התיקיות

```
src/
├─ App/                          # WinUI 3 — UI בלבד, לא מורם
│  ├─ Views/  ViewModels/  Controls/
│  └─ Resources/DesignSystem.xaml
├─ Core/                         # לוגיקה ניטרלית, בדיקה בלי Windows
│  ├─ Abstractions/              # ITweak, ISensorProvider, ISystemBroker
│  ├─ Tweaks/                    # מימוש לכל tweak
│  └─ Telemetry/Reading<T>.cs    # Value+Source+Generation+Age+Valid
├─ Broker/                       # שירות מורם — כאן ורק כאן משנים מערכת
│  ├─ IpcServer.cs
│  ├─ Journal/                   # 🔑 פנקס הביטול
│  └─ Operations/
├─ Watchdog/                     # supervisor + התאוששות מקריסה
└─ Shared/Contracts/             # חוזי IPC משותפים
```

### 5.3 החלת Registry tweak עם Rollback — קוד לדוגמה

הליבה: **פנקס write-ahead**. הכוונה נרשמת לפני הביצוע, כך שקריסה באמצע ניתנת לגילוי ולתיקון.

```csharp
// Shared/Contracts/TweakJournalEntry.cs
public sealed record TweakJournalEntry
{
    public required string TweakId      { get; init; }
    public required string Hive         { get; init; }   // "HKLM"
    public required string KeyPath      { get; init; }
    public required string ValueName    { get; init; }
    public required RegistryValueKind Kind { get; init; }
    public          object? PreviousValue { get; init; } // null = הערך לא היה קיים
    public required object  AppliedValue  { get; init; }
    public required DateTimeOffset AppliedUtc { get; init; }
    public required long    BootId      { get; init; }   // 🔑 פוסל בסיס ישן
    public          bool    Committed   { get; init; }
}
```

```csharp
// Broker/Operations/RegistryTweakOperation.cs
public sealed class RegistryTweakOperation(IJournal journal, ILogger log)
{
    public OperationResult Apply(RegistryTweak tweak)
    {
        // 1. שער תאימות — לפני כל נגיעה במערכת
        if (!tweak.Compatibility.IsSupported(out var reason))
            return OperationResult.Skipped(reason);

        using var key = OpenWritable(tweak.Hive, tweak.KeyPath);
        if (key is null)
            return OperationResult.Failed($"cannot open {tweak.Hive}\\{tweak.KeyPath}");

        // 2. לכידת המצב הקודם — כולל ההבחנה "לא היה קיים" מול "היה ריק"
        var existed  = key.GetValueNames().Contains(tweak.ValueName, StringComparer.OrdinalIgnoreCase);
        var previous = existed ? key.GetValue(tweak.ValueName) : null;

        if (existed && Equals(previous, tweak.DesiredValue))
            return OperationResult.NoChange();       // אידמפוטנטי

        // 3. כתיבה לפנקס *לפני* השינוי (write-ahead)
        var entry = new TweakJournalEntry {
            TweakId = tweak.Id, Hive = tweak.Hive, KeyPath = tweak.KeyPath,
            ValueName = tweak.ValueName, Kind = tweak.Kind,
            PreviousValue = previous, AppliedValue = tweak.DesiredValue,
            AppliedUtc = DateTimeOffset.UtcNow, BootId = SystemBoot.CurrentId,
            Committed = false
        };
        journal.Write(entry);                        // אטומי: temp + File.Replace

        // 4. השינוי בפועל
        try { key.SetValue(tweak.ValueName, tweak.DesiredValue, tweak.Kind); }
        catch (Exception ex)
        {
            journal.Remove(entry);                   // לא בוצע — הסר את הכוונה
            log.LogError(ex, "apply failed {TweakId}", tweak.Id);
            return OperationResult.Failed(ex.Message);
        }

        // 5. אימות בקריאה-חוזרת — לא סומכים על "לא נזרקה חריגה"
        var readBack = key.GetValue(tweak.ValueName);
        if (!Equals(readBack, tweak.DesiredValue))
        {
            Revert(entry);
            return OperationResult.Failed("verification failed; reverted");
        }

        journal.Commit(entry with { Committed = true });
        return OperationResult.Applied();
    }

    public OperationResult Revert(TweakJournalEntry e)
    {
        // 🔑 בסיס שנלכד לפני אתחול אינו אמין לשחזור
        if (e.BootId != SystemBoot.CurrentId && e.RequiresSameBoot)
            return OperationResult.Skipped("baseline predates reboot — refusing to restore");

        using var key = OpenWritable(e.Hive, e.KeyPath);
        if (key is null) return OperationResult.Failed("key unavailable");

        if (e.PreviousValue is null) key.DeleteValue(e.ValueName, throwOnMissingValue: false);
        else                          key.SetValue(e.ValueName, e.PreviousValue, e.Kind);

        journal.Remove(e);
        return OperationResult.Reverted();
    }

    /// באתחול: משלים כל שינוי שנקטע באמצע.
    public void RecoverIncomplete()
    {
        foreach (var e in journal.ReadAll().Where(x => !x.Committed))
        {
            log.LogWarning("uncommitted tweak {TweakId} — reverting", e.TweakId);
            Revert(e);
        }
    }
}
```

**חמשת העקרונות שהקוד הזה מקודד** (כולם נלמדו ממה שנמצא בפועל ב-Winhanced):

1. **פנקס write-ahead** — הכוונה נרשמת לפני הפעולה, כך ש-`RecoverIncomplete()` יכול לנקות
   אחרי קריסה. זו ההרחבה של מה ש-`wake-provision-state.json` עושה.
2. **הבחנה בין "לא היה קיים" ל"היה ריק"** — `PreviousValue is null` → **מחיקה**, לא כתיבת
   ריק. בלי זה, Revert משאיר ערך שלא היה שם מעולם.
3. **`BootId`** — ישירות מ-`BootUtcTicks` של Winhanced. גיבוי שיודע לסרב.
4. **אימות בקריאה-חוזרת** — "לא נזרקה חריגה" אינו הוכחה שהערך נכתב. זה בדיוק
   [[verify-a-transform-by-counting-its-effect]] של הפרויקט הזה.
5. **שער תאימות לפני נגיעה** — לא לבצע ואז לגלות.

### 5.4 מדידה עם מטא-דאטה (ישירות מ-`whservice.log`)

```csharp
public readonly record struct Reading<T>(
    T       Value,
    string  Source,          // "amd-adlx-direct" | "windows-nt-per-core"
    int     ProviderGeneration,
    TimeSpan Age,
    bool    IsValid)
{
    public bool IsUsableFor(TimeSpan maxAge) => IsValid && Age <= maxAge;
}
```

**כלל:** שום לוגיקת בקרה לא פועלת על `Reading<T>` בלי `IsUsableFor()`. זה מה שמונע מהמערכת
להגיב לנתון מת.

### 5.5 מה לאמץ ומה לא

**לאמץ:**
- broker מורם + UI לא-מורם (הבידוד הנכון)
- טלמטריה עם source/generation/age/valid
- פנקס ביטול ממוקד + baselines עם BootId
- הפרדת `Supports*` מ-`Enabled*`
- בדיקת זמינות API בפועל, לא רק מספר בנייה
- `AlwaysUseFallback` על כל חומר שקוף
- DeepIdle — הקפאת אנימציות בחלון לא-פעיל
- MemWatch — טלמטריה של מהנדס

**לא לאמץ:**
- מגן JIT (עלות בלי תמורה)
- הזרקת דרייבר קרנל אלא אם אין ברירה
- ניהול שינויי מערכת בלי נקודת שחזור כגיבוי-על (ראו §2.3 — זו החולשה של המודל)

**להוסיף מעבר ל-Winhanced:**
- **נקודת שחזור אחת לפני הפעלה ראשונה** (`SRSetRestorePoint`) — רשת ביטחון לפנקס עצמו
- **ייצוא/ייבוא פנקס** — כדי שמשתמש יוכל להחזיר מצב גם אחרי התקנה מחדש

---

## נספח: מקורות הראיה

| טענה | מקור | ודאות |
|---|---|---|
| .NET 8 + WinUI 3 | `runtimeconfig.json`, `deps.json` | ודאי |
| רשימת P/Invoke | ארגומנטים של `[DllImport]` (מטא-דאטה) | ודאי |
| GUID-ים של COM | ארגומנטים של `[Guid]` | ודאי |
| 121 enums | מטא-דאטה | ודאי |
| 100 מאפייני הגדרות | מטא-דאטה + `appsettings.json` חי | ודאי |
| מערכת העיצוב | `DesignSystem.xbf` (75 מחרוזות) | ודאי |
| מנגנון Revert | קבצי runtime על הדיסק | ודאי |
| מודל התהליכים | `watchdog.log` | ודאי |
| טלמטריה | `whservice.log` | ודאי |
| חסימה לפי גרסה | `app_*.txt` | ודאי |
| RyzenAdj לא בשימוש | תלויות חסרות + לוגיקת ה-BAT | ודאי |
| אין System Restore | היעדר `srclient` ברשימת P/Invoke | ודאי (ממצא שלילי) |
| נתיבי Registry ספציפיים | — | **לא ניתן לשחזור** (מוצפן) |
| שאילתות WMI ספציפיות | — | **לא ניתן לשחזור** (מוצפן) |
| לוגיקת Smart Launch Watcher | — | **לא ניתן לשחזור** (מוצפן; גם אסור משפטית) |

**מפה משפטית:** מבנה, ארכיטקטורה ו-IA הם עיצוב נצפה וניתן ללמידה. אסור לשחזר: נכסי ה-UI/XAML
המקומפל של Winhanced, מאגר ה-Smart Profiles, וקוד המימוש של Smart Launch Watcher.
