# Winhanced — ניתוח הנדסי מלא (Reverse Engineering)

**גרסאות שנבדקו:** 0.9.9.3 (המותקנת) + **0.9.9.7** (`Winhanced-Installer-0.9.9.7.exe`, 782 MB, נחלץ
לקריאה בלבד — **לא הורץ ולא הותקן**).
**תאריך:** 2026-08-16 · **שיטה:** ניתוח סטטי בלבד, קריאה-בלבד.

---

## 0. גבול הראיות — לקרוא לפני הכול

זהו החלק החשוב ביותר בדוח, כי הוא קובע אילו תשובות הן **עובדה** ואילו הן **הסקה**.

### 0.1 המוצר מוגן ב-Protector מסחרי עם הצפנת גופי-מתודות

כל ארבעת האסמבליים המנוהלים — `Winhanced.dll` (19.5 MB), `Winhanced.Shared.dll`,
`DynamicTDP.dll`, `HardwareControl.dll` — נושאים את אותו מנגנון הגנה:

| סימן | ערך |
|---|---|
| Namespace של ה-Protector | `Xy9Ac91TTPsPd5mC4M` |
| Bootstrap | `CIbUAhPuLA8nvrkWee.ExGYDduSGq()` — נקרא מכל `static ctor` בתוכנה |
| שיטה | **JIT hook** — 6 P/Invokes מעורפלים ל-`libclrjit`; גופי המתודות מפוענחים רק בזמן קומפילציה |
| סימן משני | `[MethodImpl(MethodImplOptions.NoInlining)]` על **כל** חבר; שדות פרטיים בשמות זבל |

**אומת על שתי הגרסאות** — 0.9.9.3 ו-0.9.9.7 מתנהגות זהה. זו החלטה ארכיטקטונית קבועה, לא תקלה
נקודתית.

### 0.2 מה שורד ומה נהרס — נמדד, לא משוער

הרצתי בדיקת-בדיקה (`probe_strings.py`) שסופרת מופעים של 27 מחרוזות-מפתח בשתי הקידודים:

| שורד ✅ (עובדה ניתנת לציטוט) | נהרס ❌ (בלתי-נגיש סטטית) |
|---|---|
| Namespaces, שמות טיפוסים, היררכיה, ממשקים | **כל גופי המתודות** (`return null;` / `return true;` / ריק) |
| שמות מתודות ציבוריות/פנימיות + **חתימות מלאות** | **כל מחרוזת בתוך מתודה** — נתיבי Registry, שאילתות WMI, שורות פקודה |
| שמות Properties, שמות Enum **וערכיהם** | ערכי `static readonly` שמאותחלים בקוד |
| **ארגומנטים של Attributes** — `DllImport("user32.dll")`, `Guid("…")`, `MarshalAs` | לוגיקת האלגוריתמים |
| ערכי `const` | |

תוצאת ההוכחה: `SOFTWARE\Microsoft\Windows` = **0 מופעים**, `Win32_VideoController` = **0**,
`powercfg` = **0**, `schtasks` = **0**, `ryzenadj` = **0** — בשתי הקידודים, בשתי הגרסאות.

### 0.3 מה זה אומר לגבי חלקים 1-2 של הבריף

> **את נתיבי ה-Registry המדויקים, שאילתות ה-WMI המדויקות ושורות ה-PowerShell המדויקות — אי אפשר
> לקרוא מהבינארי. מי שיטען שהוא קרא אותם משם, טועה או ממציא.**

מה שכן ניתן, ובגדול: **משטח ה-P/Invoke האמיתי** (ה-Attributes שורדים), **מפת ה-Backends המלאה**,
**כל ה-Enums עם ערכיהם**, ו-**התיעוד הרשמי של האלגוריתם** (ראו §0.4).

### 0.4 המקורות הקריאים לחלוטין — שהם מפצים על הכול

| מקור | מה יש בו |
|---|---|
| **`whservice/DynamicTDP.xml`** (16 KB) | 🔑 **קובץ תיעוד ה-XML של האסמבלי** — `<summary>` מלא לכל טיפוס וחבר. האלגוריתם, במילים של המפתח עצמו, ללא שום הגנה |
| 99-113 קבצי `.xbf` | כל עץ ה-UI, ה-IA, וטוקני העיצוב (מפוענחים ע"י `games/winhanced/work/xbf.py`) |
| `Config/smart-launch-watcher.json` | 20 תבניות חסימה + כל פרמטרי הכוונון |
| `readjustService.ps1` (24 KB) + `readjust.py` + `pmtable-example.py` | קוד RyzenAdj אמיתי (LGPL, של Falco Schaffrath) |
| `installServiceTask.bat` / `uninstallServiceTask.bat` | פקודות `SCHTASKS` ו-`reg` אמיתיות |
| `CustomCapability.SCCD` | היכולת המותאמת של Windows |
| `hud/*.msixbundle` → `AppxManifest.xml` | ארכיטקטורת ה-HUD במלואה |
| `Assets/RTSS/*.ovl` | פריסות RTSS ב-INI רגיל |
| `Assets/Power/Winhanced_powerplan.pow` | תוכנית צריכת-חשמל מיוצאת |
| `workloads.*.json` (6 קבצים) | פרופילי עומס |
| `store_seed.db` (167 MB) + `spine_seed.db` (27 MB) | SQLite רגיל, לא מוצפן |

**⚠️ מלכודת שנמנעה:** העותק המותקן (0.9.9.3) מכיל את **תיקון העברית שלנו מ-Track A** ב-4 קבצים.
כל פענוח ה-XBF נעשה מגיבויים נקיים (`games/winhanced/backup/`) ומהמתקין החדש — ולא מהעותק החי.

---

## 1. ארכיטקטורה, טכנולוגיה ואינטגרציה עם Windows

### 1.1 ה-Tech Stack (עובדה — מ-`runtimeconfig.json` + `deps.json`)

```json
{ "tfm": "net8.0",
  "frameworks": [ "Microsoft.NETCore.App 8.0.0", "Microsoft.WindowsDesktop.App 8.0.0" ] }
```

| שכבה | הטכנולוגיה |
|---|---|
| Runtime | **.NET 8** (`net8.0`), framework-dependent |
| UI | **WinUI 3 / Windows App SDK 2.0.1**, XAML מקומפל ל-`.xbf` |
| גרפיקה | **Win2D** (`Microsoft.Graphics.Canvas`) + **ComputeSharp.D2D1** — שיידרים ב-C# |
| אנימציה | `CommunityToolkit.WinUI.Lottie` + `AnimatedWebPControl` (WebP מונפש) |
| AI מקומי | `Microsoft.ML.OnnxRuntime` + `onnxruntime.dll` (21.6 MB) + `Microsoft.Graphics.Imaging` (כולל `ImageObjectRemover`) |
| נתונים | SQLite (`Microsoft.Data.Sqlite`) + **SQLCipher** (`SQLitePCLRaw.bundle_e_sqlcipher`) |
| חומרה | `LibreHardwareMonitorLib`, `HidSharp`, `HidLibrary`, `DiskInfoToolkit`, `ADLXCSharpBind` (AMD), `ZD.IGCLWrapper`/`ZD.PlatformControl` (Intel), `NPUDetect` |
| טלמטריה | **`Microsoft.Diagnostics.Tracing.TraceEvent`** — ETW |
| Web | `AngleSharp` (פרסור HTML), `Newtonsoft.Json` |
| חיצוני | `discord_partner_sdk.dll` (9.6 MB), `RTSSSharedMemoryNET` |
| סה"כ | **217 חבילות NuGet / 225 ספריות** |

### 1.2 מודל התהליכים — 8 בינאריים נפרדים

זו לא אפליקציה אחת. זו **מערכת**:

| בינארי | גודל | תפקיד |
|---|---:|---|
| `Winhanced.exe` + `Winhanced.dll` | 383 KB + 19.5 MB | ה-Shell הראשי (WinUI 3) |
| **`whservice/`** | ~40 MB | **שירות Windows עצמאי (self-contained .NET)** — הבעלים של החומרה |
| `WinhancedWatchdog.exe` | **79.9 MB** | Watchdog עצמאי |
| `WinhancedFseBridge.exe` | 147 KB | גשר Fullscreen-Exclusive |
| `WinhancedMaintenanceHost.exe` | 147 KB | מארח תחזוקה |
| `WinhancedRuntimeRepair.exe` | 310 KB | תיקון runtime |
| `start/Winhanced-Shell.exe` | 142 KB | משגר ה-Shell |
| `hud/WinhancedHUD*.msixbundle` | 4.1 MB | **ווידג'ט Xbox Game Bar** (UWP נפרד) |

### 1.3 🔑 שתי יכולות Windows שקובעות את כל הארכיטקטורה

**א. `CustomCapability.SCCD`** — קובץ SCCD חתום:

```xml
<CustomCapability Name="Microsoft.appCategory.gamingHome_8wekyb3d8bbwe" />
<AuthorizedEntities AllowAny="true" />
```

**`gamingHome` היא היכולת הרשמית של Windows שמאפשרת לאפליקציה להירשם כ"בית משחקים" —
אותה יכולת שחוויית ה-Xbox Full Screen משתמשת בה.** זה מה שהופך את Winhanced ל-Shell אמיתי של
המערכת ולא לחלון עוד. הקובץ `Winhanced.Identity.msix` (+`.cer`) הוא **חבילת Sparse/Identity** —
כך אפליקציית Win32 משיגה זהות-חבילה כדי בכלל להיות זכאית ליכולת הזו.

**ב. ה-HUD הוא ווידג'ט Xbox Game Bar רשמי** — מ-`AppxManifest.xml`:

```xml
<uap3:AppExtension Name="microsoft.gameBarUIExtension" Id="Widget1" …>
  <GameBarWidget Type="Standard">
    <Window><AllowForegroundTransparency>true</AllowForegroundTransparency>
      <Size><Height>625</Height><Width>460</Width> …
```

### 1.4 ⚠️ תשובה ישירה: **אין Process Injection ואין Hooks**

זו אחת המסקנות החשובות בדוח, והיא מגובה בשלוש ראיות עצמאיות:

1. ה-HUD רוכב על **נקודת ההרחבה הרשמית** של Game Bar (למעלה) — לא על הזרקה.
2. `WinhancedOverlayBridge.dll` יושב ב-`Assets/RTSS/` — כלומר הוא **תוסף של RTSS**, וקבצי
   ה-`.ovl` הם INI רגיל שמצהיר `Provider=AIDA` עם `ID=WINHANCED_OVERLAY_MODE`. כלומר Winhanced
   מפרסם נתונים ל-RTSS דרך **ממשק ה-shared-memory התואם-AIDA64**, ו-RTSS (שכבר מוזרק ממילא)
   מצייר. Winhanced עצמו לא נוגע בתהליך המשחק.
3. ה-Smart Launch Watcher (§2.4) עובד ב-**Polling** על חלונות ותהליכים — לא ב-hooks.

זהו ניגוד חד ל"אופטימייזרים" טיפוסיים, וזו הסיבה שהמוצר יכול לחיות לצד Anti-Cheat.

### 1.5 משטח ה-P/Invoke האמיתי (ה-Attributes שורדים את ההגנה)

~200 ייבואים על פני 28 DLL-ים מקומיים. הבולטים: `user32.dll` (חלונות, קלט, foreground),
`kernel32.dll`, `dwmapi.dll` (Mica/Acrylic/פינות), `shell32.dll`, `advapi32.dll` (שירותים/Registry),
`powrprof.dll` (תוכניות חשמל), `setupapi.dll`+`cfgmgr32.dll` (התקנים), `hid.dll`, `ntdll.dll`,
`xinput1_4.dll`, `winmm.dll`, `dxgi.dll`/`d3d11.dll`, `wtsapi32.dll` (סשנים), `psapi.dll`.

**ממשקי COM ששרדו עם ה-GUID שלהם** — למשל `IPolicyConfig`
(`f8679f50-850a-41cf-9c72-430f290290c8`) + `CPolicyConfigClient`
(`870af99c-171d-4f9e-af0d-e63df40c2bc9`) — ה-API הפרטי הלא-מתועד של Windows להחלפת התקן השמע
הדיפולטיבי. הוכחה שהמוצר משתמש ב-COM פרטי, לא ב-PowerShell, למשימות כאלה.

---

## 2. מיפוי תכונות מלא

### 2.1 🔑 שכבת החומרה — `HardwareControl.dll`, המפה המלאה

מבנה ה-namespace `Winhanced.HardwareControl.Backends` שרד במלואו. זו התשובה הטובה ביותר
לשאלה "איזה ערך במערכת הוא משנה":

| יצרן | מסלול הכתיבה | הראיה (שמות טיפוסים) |
|---|---|---|
| **AMD גנרי** | **PawnIO** (דרייבר kernel, GPL) | `AmdPawnIoBackend`, `AmdPawnIoAuthorization`, `AmdApuFamily`, `AmdPowerEnvelope`, `AmdTdpCeilings` |
| **AMD SMU** | תיבת-דואר SMU + **PM Table** | `RyzenSmuPmTableSession/Decoder/Snapshot`, `RyzenSmuLimitReadback`, `RyzenSmuDeferredLimitVerifier`, `RyzenSmuPackagePowerPolicy` |
| **Intel** | **MSR** (RAPL) | `IntelMsrTdpBackend`, `IntelMsrAuthorization`, `IntelApuFamily`, `IntelPowerEnvelope`, `IntelTdpCeilings` |
| **ASUS** | ACPI/ATK + WMI + SMU | `AsusAcpiTdpBackend`, `AsusAcpiFanBackend`, `AsusZ13WmiTdpBackend`, `AsusAllySmuPrimaryBackend`, `AsusDstsReadCapability`, `AsusPptPolicy/Clamps/Envelope` |
| **Lenovo** | WMI (GameZone) + EC | `LenovoWmiBackend`, `LenovoGameZonePowerModeBackend`, `LegionGo2EcFanBackend`, `LenovoSmuPrimaryBackend`, `LegionWmiFanPolicy` |
| **MSI** | WMI + ACPI | `MsiWmiBackend`, `MsiAcpiLocator`, `MsiClawFanBackend`, `MsiClawOverBoost`, `MsiPowerLimitPolicy` |

**ה-Enum שמסכם הכול (ערכים אמיתיים):**

```csharp
public enum HardwareTdpRoute {
    Unavailable, GenericAmdPawnIo, AsusAtkAcpi, AsusGz302Wmi,
    MsiClawWmi, LenovoWmi, LenovoSmuPawnIo, AsusAllySmuPawnIo, GenericIntelMsrPawnIo }
```

**קטלוג המכשירים הנתמכים (אמיתי):**

```csharp
public enum HandheldModel { None, SteamDeck, RogFlowZ13, OneXPlayerApex, OneXFlyF1Pro,
    OneXFlyF1, OneXPlayer3, AyaneoAirPlus, GpdWin4, GpdWin5, AntecCoreHs }
public enum LegionGoModel { None, LegionGo, LegionGo2, LegionGoS }
public enum MsiClawModel  { None, A1M, A2Vm, A8, Claw8G3, Claw8Ex, UnsupportedClaw }
public enum AmdApuFamily  { Unknown, Z1Extreme, Z2, Z2Go, Z2Extreme, Z2A, StrixHalo }
public enum IntelApuFamily{ Unknown, PantherLakeG3, PantherLakeG3Extreme }
public enum HardwarePlatformPowerMode { Quiet = 1, Balanced = 2, Performance = 3, Custom = 255 }
public enum HardwareFanMode { Firmware, Silent, Balanced, Turbo, Custom }
```

**זיהוי מכשיר עם רמת ודאות** — `DeviceIdentityConfidence { Unknown, HintOnly, Family, Model,
Variant, Ambiguous }`. כלומר: התוכנה **יודעת שהיא לא בטוחה**, ומתנהגת בהתאם. זו התשובה
לשאלה "איך היא מונעת קריסה בשינוי רגיש" — היא לא כותבת לחומרה שהיא לא זיהתה ברמת Model.

### 2.2 🔑 DynamicTDP — האלגוריתם, בתיעוד של המפתח עצמו

מ-`DynamicTDP.xml`, מצוטט:

> **"Pressure is advisory input only; RTSS frametime remains the DynamicTDP target authority."**

**עקרונות שתועדו במפורש:**

| עיקרון | הציטוט |
|---|---|
| מקור-אמת יחיד | frametime מ-RTSS הוא סמכות היעד; ניצולת CPU/GPU היא **וטו בלבד** |
| הווטו לעולם לא מעלה הספק | *"This policy never requests or raises power"* |
| בחירת אות | GPU ראשי מעל **25%**; CPU מצרפי כ-fallback ב-25% ומטה או כשה-GPU לא שמיש. **max-core CPU דיאגנוסטי בלבד** — *"a rotating busy core is not proof that package power cannot decrease"* |
| חסינות לרעש | GPU משתמש ב**חציון** אחרון כדי ש"פיק בודד לא ייצור רצפה נסתרת ותקתוק שקט בודד לא יפתח חור-כתיבה"; CPU מצרפי נחשף רק אחרי **שתי דגימות** גבוהות |
| Latch | וטו טרי נשמר לפרק זמן קצר, כי *"Sampler updates do not arrive atomically"* |
| **Fail-open** | אם אין טלמטריה תקפה — ההחלטה נכשלת **פתוחה**, *"so telemetry cannot become a hidden floor"* |
| חלון סטטיסטי | `RollingFrameWindow` — 250ms, 1,024 רשומות, **allocation-free** |
| סריאליזציית כתיבות | `TdpWritePump` — *"never cancelled or overlapped"*; רק בקשות **שטרם התחילו** מתמזגות |
| זהות טרנזקציה | Epoch + Revision + Lease-generation מזהים פעולה מאושרת אחת |
| התייצבות | **500ms מינימום אוניברסלי**; רמז תאימות של המכשיר תקף רק מ-501ms ומעלה |
| הפרדת אחריות | *"WHService initializes and authorizes the endpoint before passing it to DynamicTDP; **the algorithm never constructs a device backend**"* |

**אימות כתיבה בארבע דרגות** — `TdpWriteVerification { Rejected, BackendAccepted,
RegisterVerified, ResponseValidated }`, בתוספת `TdpBehavioralVerification` ו-
`PackagePowerAgreementPolicy` (השוואת ההספק **הנמדד** מול המבוקש). כלומר: לא מספיק ש-API החזיר
הצלחה — התוכנה בודקת שהחומרה **באמת** השתנתה.

### 2.3 מקור ה-TDP הפתוח שנשלח עם המוצר

`readjustService.ps1` (24 KB, **LGPL, Falco Schaffrath**) — לא מוגן, קריא במלואו. מגדיר 50+
P/Invokes ל-`libryzenadj.dll` (`set_stapm_limit`, `set_fast_limit`, `set_slow_limit`,
`set_tctl_temp`, `set_apu_skin_temp_limit`, `set_max_gfxclk_freq`, …), מעתיק
`WinRing0x64.sys` לצד ה-exe, ומנטר `GetSystemPowerStatus` + מיקום מחוון ההספק.

`installServiceTask.bat` מראה את מנגנון ההתקנה **המדויק** (וזה קוד קריא, לא משוער):

```bat
SCHTASKS /Create /TN "AMD\RyzenAdj" /XML "%~dp0RyzenAdjServiceTask.xml" /F
SCHTASKS /run   /TN "AMD\RyzenAdj"
```
```bat
:: uninstall
reg query  HKCU\Software\HWiNFO64\Sensors\Custom\RyzenAdj
reg delete HKCU\Software\HWiNFO64\Sensors\Custom\RyzenAdj
SCHTASKS /delete /TN "AMD\RyzenAdj"
```

⚠️ **הערה חשובה:** אלה קבצי RyzenAdj **המקוריים** שנשלחים כנכס. הם **לא** מוכיחים ש-Winhanced
עצמה מריצה אותם — היא מדברת עם החומרה דרך `HardwareControl.dll` (§2.1). הם כן מוכיחים מה
זמין לה ומהי משפחת ה-API.

### 2.4 Smart Launch Watcher (`Config/smart-launch-watcher.json`) — קריא לחלוטין

חוסם 20 סוגי חלונות חוסמים בזמן השקת משחק, בקטגוריות:
`redistributables` · `anticheat` · `cloudsave` · `auth` · `modals` · `launcher`.

```json
"monitoringIntervalMs": 1000, "maxMonitoringTimeMs": 90000, "splashRestoreDebounceMs": 500
```

חמישה מקורות אות עם קצבים נפרדים: `windowSweepIntervalMs: 500`,
`processTreeIntervalMs: 1500`, `foregroundWindowIntervalMs: 250`.

**⚠️ תזכורת משפטית:** רק **מבנה ה-JSON** גלוי. לוגיקת המימוש עצמה מוגנת ואסורה לשכפול
(ראו את מפת המותר/אסור ב-`winhanced_servers_report.md`).

### 2.5 100 ההגדרות (`AppSettings` — שמות וטיפוסים אמיתיים, ערכי ברירת-מחדל נמחקו)

בדיוק **100 Properties ציבוריים**. הקבוצות: מודל TDP משולש (Sustained/Burst/Fast), דגלי
תכונות GPU לפי יצרן (AFMF, RSR, AntiLag, Boost, EnduranceGaming, IntelFrameGeneration),
עקיפות FSE, מתגי מראה, ודליי wishlist/calendar/news.

### 2.6 מה שלא נמצא — ואמירה כנה

**לא נמצא בשום מקום** מנגנון מפורש של **System Restore point** או **גיבוי Registry** לפני
שינוי. מה שכן קיים, ובגדול, הוא **אימות כתיבה** (§2.2) ו-`WinhancedRuntimeRepair.exe`. ייתכן
שקיים גיבוי ושמו לא נחשף בגלל ההגנה — אבל **אין לי ראיה לו**, ולא אטען שיש.

---

## 3. UI/UX, עיצוב ואפקטים

### 3.1 🔑 מנוע האפקטים — `GlassLabPage.xbf` מסגיר הכול

בתוך המוצר יש **עמוד דיאגנוסטיקה פנימי** לצינור השיידרים. המחרוזות שלו:

```
Glass Lab — shader pipeline diagnostic
using:Microsoft.Graphics.Canvas.UI.Xaml
Panel A: raw CanvasControl + bitmap (no shader)
BaselineCanvas | ShaderCanvas | RimShaderCanvas | MinimalRimCanvas | StatusLabel | Consolas
```

כלומר ה"Living Glass" הוא **Win2D `CanvasControl` + פיקסל-שיידרים של D2D1 שנכתבו ב-C#
(ComputeSharp)**, עם **שיידר Rim** ייעודי לשפה המבריקה של הכרטיסים — והמפתחים מחזיקים
מסך-השוואה בין Baseline / Shader / Rim / MinimalRim. זו התשובה הישירה לשאלת האפקטים.

בנוסף, ה-HUD רושם In-Process את **כל** מנוע ה-Effects של Win2D — כולל
`GaussianBlurEffect`, `ShadowEffect`, `BlendEffect`, `ColorMatrixEffect`, `TurbulenceEffect`,
`DisplacementMapEffect`, `HdrToneMapEffect`, `PixelShaderEffect`.

### 3.2 מערכת העיצוב (`Resources/DesignSystem.xbf` — 75 טוקנים)

| קטגוריה | הטוקנים |
|---|---|
| טיפוגרפיה | **Inter** — Light / Medium / SemiBold; גדלים **2 · 6 · 12 · 14 · 16 · 18 · 20 · 22 · 24** |
| סגנונות טקסט | `H1/H2/H3TextStyle`, `Body1/Body2TextStyle`, `SubtextStyle` |
| אייקונים | **Segoe MDL2 Assets** + **Segoe Fluent Icons** |
| חומר | `AcrylicBrush` עם `TintColor` / `TintOpacity` / `TintLuminosityOpacity` / `AlwaysUseFallback` |
| מברשות זכוכית | `GlassButtonBrush`, `GlassOnlyAcrylicBrush(+BG)`, `GameDetailsGlassAcrylicBrush`, `BladeSurfaceAcrylicBrush`, `StoreTileGlassFlatBrush`, `GlowDiffusionBrush` |
| מצב בהיר/כהה | זוגות מפורשים: `CardSurfaceLight/DarkBrush`, `CardFocusGlowBrushLight/Dark`, `NavHeaderBrushLight/Dark` |
| ריווח | `SpacingXXSmall → XSmall → Small → Medium` + `SpacingOffsetCenter` |
| רדיוסים | `CornerRadiusSmall/Medium/Large` + פר-רכיב: `GameCard`, `FilterCard`, `DiscordCard`, `GlassPill` (+גרסאות `…GlowCornerRadius`) |
| צבע מערכת | **`SystemAccentColor`** — צבע ההדגשה של Windows |
| רכיבים | `SmartChip{Style,IconStyle,TextStyle,TextLargeStyle,Accent*}`, `StatusIndicator{Icon,Button}Style`, `PrimaryCTAButtonStyle`, `GlassPillPowerButtonStyle` |

### 3.3 מבנה ה-Shell (`MainWindow.xbf` — 283 מחרוזות)

מלמעלה למטה:
`BloomCanvas` → `BackgroundImageA`/`B` (הצלבה חוצה) + `AcrylicVeil` → **`BumperPillNavigation`**
(LB ‹ גלולות › RB עם `GlowUnderline`) → **`PinnedSecondaryNavHost`** (LT ‹ שבבי סינון › מיון ▾
+ מונה טווח › RT) → `GlassRailHost` + `HomeGameInfoPanel` לצד `RecentGames` (ItemsRepeater אופקי)
→ **`NavFooterGrid`** (סרגל רמזי הבקר).

**אנטומיית כרטיס משחק:**
`ShadowHost > FocusableCardButton > CardChrome + TintOverlay + CardSpecularRim + BoxArtImage +
GlassSourceBadge + FocusGlowBorder + FocusScaleTransform`
עם `FocusStates { Unfocused, Focused, PointerFocused }` — כלומר **פוקוס-בקר ופוקוס-עכבר הם שני
מצבים נפרדים**, וזה מה שגורם לניווט בבקר להרגיש נכון.

שכבות נוספות: `GameSplashLayer`, `StreamingLaunchOverlay`, `FrameStatsOverlay`.

### 3.4 מה חדש ב-0.9.9.7 (99 מסכים)

`Controls/Blades/BladeControl` (מטאפורת ה-Blades של Xbox 360 — `AccentBar`, `AccentGlow`,
`TabLayer`) · `Views/SmartProfiles/SmartProfileItemView` · `Pages/XCloudCatalogPage` +
`XCloudStreamWindow` · `ChiakiStreamWindow` (PS Remote Play) · `MoonlightStreamWindow` +
`SunshineCredentialsDialog` · `GeForceNowCaptureDialog` · `PaddleMappingCanvas` ·
`Plugins/GameLibraries/Epic/EpicLoginView` (**ארכיטקטורת תוספים לספריות משחקים**) ·
`AutoPilotReadyDialog` · `MemoryWarningDialog` · `StorageManagerDialog` · `WhatsNewPage`.

### 3.5 🔑 דפוס UX שראוי לחיקוי — `PerformanceSettingsPage`

כל כרטיס-מתג מלווה ב:
```
DetailMediaImage / AnimatedWebPControl (וידאו הדגמה)  +
DetailDescriptionText:   "What you get:" / "Trade-off:" / "Alternative:"
```

**התוכנה מצהירה על המחיר של כל שינוי, לא רק על התועלת.** זה בדיוק מה שמפריד בין כלי-מערכת
אמין ל"אופטימייזר". התכונות עצמן: `Winhanced device control`, `Enhanced sleep/wake`,
`Replace Xbox app as launcher for FSE`, `Card specular highlights`,
`Desktop mode launch at startup`, `FSE diagnostics logging`,
`Remap hardware key to Gamebar/HUD`.

### 3.6 תפריט ההפעלה (`PowerMenuDialog`) — הטקסט המדויק

| שורה | כותרת-משנה |
|---|---|
| Sleep | Low power, quick resume |
| Hibernate | Zero power, saves state to disk |
| Restart | Restart this device |
| Shut down | Power off this device |
| **Desktop Mode** | **Switch to Windows desktop** |
| Quit Winhanced | Exit application |

---

## 4. ביצועים, בטיחות ותחזוקה

### 4.1 איך היא מונעת קריסה — חמש שכבות, כולן מגובות בראיות

1. **זיהוי לפני כתיבה** — `DeviceIdentityConfidence` + `DeviceIdentityCatalog`; ללא רמת
   Model/Variant אין כתיבה לחומרה.
2. **תקרות מובנות** — `AmdTdpCeilings`, `IntelTdpCeilings`, `AsusPptClamps`,
   `HardwareTdpRangeResolver`, `DevicePowerLimits`.
3. **הפרדת אחריות** — WHService מאתחל **ומאשר** את נקודת-הקצה; האלגוריתם לעולם לא בונה
   Backend בעצמו.
4. **אימות אחרי כתיבה** — 4 דרגות `TdpWriteVerification` + `TdpBehavioralVerification` +
   `PackagePowerAgreementPolicy` (הספק נמדד מול מבוקש) + `RyzenSmuDeferredLimitVerifier`.
5. **Fail-open מכוון** — טלמטריה חסרה לעולם לא הופכת ל"רצפה נסתרת".

בנוסף: `InstanceGuard` (מופע יחיד), `AsusFirmwareCurveValidator` (ולידציית עקומת מאוורר מול
הקושחה), `TdpMonotonicClock` (זמן מונוטוני משותף — חסין לשינויי שעון), `TdpWriteResultValidator`.

### 4.2 טלמטריה בזמן אמת

`LibreHardwareMonitorLib` (חיישנים) · `Microsoft.Diagnostics.Tracing.TraceEvent` (**ETW**) ·
`RTSSSharedMemoryNET` (frametime) · `DiskInfoToolkit` (SMART) · `ADLXCSharpBind` (AMD) ·
`ZD.IGCLWrapper` (Intel) · `NPUDetect` · `HidSharp`/`HidLibrary`.
הנתונים מוצגים דרך `FrameStatsOverlay` בתוך האפליקציה, ודרך ווידג'ט ה-Game Bar +
פריסות RTSS (`Winhanced-DynamicTDP-1/2`, `Winhanced-Level-1/2/3`) מחוצה לה.

### 4.3 תחזוקה

`WinhancedWatchdog.exe` (79.9 MB, עצמאי) · `WinhancedMaintenanceHost.exe` ·
`WinhancedRuntimeRepair.exe` · `UpdateCenterPage` ב-UI · `installer-metadata.json`
(`{"Version":"0.9.9.7","CreatedUtc":1786448791}`) · `Assets/Power/Winhanced_powerplan.pow`
(תוכנית חשמל מיוצאת ומותאמת, בשם "Winhanced").

### 4.4 זיהוי גרסת Windows

ה-HUD דורש `MinVersion 10.0.19041.0`; נבנה על `10.0.26100.8276`. יכולת `gamingHome` היא עצמה
שער-גרסה. גילוי היכולות בפועל הוא **per-device** (§4.1) ולא per-build — וזו החלטה נכונה יותר.

---

## 5. תוכנית שחזור (Replication Blueprint)

### 5.1 מה לאמץ ומה לא — ההמלצה שלי

| לאמץ ✅ | לא לאמץ ❌ |
|---|---|
| הפרדת **שירות** (חומרה) מ-**UI** — קריטי | Protector עם הצפנת JIT — עלות תחזוקה ואפס ערך למשתמש |
| אימות-אחרי-כתיבה בדרגות | 8 תהליכים נפרדים — מורכבות מיותרת בגרסה ראשונה |
| **Fail-open** על טלמטריה חסרה | Watchdog של 80 MB |
| `DeviceIdentityConfidence` לפני כל כתיבה | |
| ווידג'ט Game Bar במקום הזרקה | |
| דפוס ה-UX "What you get / Trade-off / Alternative" | |

### 5.2 מחסנית מומלצת

**C# + .NET 8/9 + WinUI 3** (Windows App SDK) — אותה מחסנית, מהסיבות הנכונות: Win2D
ל-`CanvasControl`, ComputeSharp.D2D1 לשיידרים, `Microsoft.Extensions.Hosting` ל-Worker Service,
SQLite (+SQLCipher לנתוני משתמש), `LibreHardwareMonitorLib` לחיישנים.

> **⚠️ בהקשר של הפרויקט שלנו:** הנתיב המאושר הוא **Base 2 = מארח נייטיב דק שמארח את ה-React
> הקיים ב-WebView2** (`unified_platform_PIPELINE.md`), **לא** שכתוב UI ל-WinUI 3. הבלוקים
> שלהלן הם התשובה לבריף התיאורטי; הם **לא** משנים את ההחלטה שהתקבלה.

### 5.3 מבנה תיקיות

```
MyShell/
├─ MyShell.App/                  WinUI 3 — UI בלבד, אפס גישה לחומרה
│  ├─ Resources/DesignSystem.xaml     טוקנים: צבע · טיפוגרפיה · ריווח · רדיוס
│  ├─ Views/  Controls/  Dialogs/
│  └─ Effects/GlassRimShader.cs       ComputeSharp.D2D1
├─ MyShell.Service/              Worker Service (רץ מוגבה)
│  ├─ Hardware/ITdpBackend.cs         חוזה נקי
│  ├─ Hardware/Backends/…             מימוש פר-יצרן
│  ├─ Tweaks/ITweak.cs                Apply / Revert / IsApplied
│  └─ Safety/{RestorePoint,RegistryBackup,WriteVerifier}.cs
├─ MyShell.Contracts/            רשומות משותפות + IPC (named pipe / JSON-RPC)
└─ MyShell.Tests/
```

### 5.4 Tweak בטוח עם Rollback — הקוד שהבריף ביקש

הנקודה המרכזית: **ה-Revert נשמר לפני ה-Apply, מאומת אחרי ה-Apply, ולעולם לא מנחש את המצב
המקורי.** זה בדיוק העיקרון שכבר מוכח אצלנו ב-`launcher-build` (גיבוי מחוץ לתיקיית היעד,
כתיבה אטומית, revert byte-exact).

```csharp
// Contracts/ITweak.cs
public interface ITweak {
    string Id { get; }
    bool   IsSupported(SystemInfo sys);       // חוסם build/מכשיר לא נתמך
    Task<TweakState> ReadAsync();             // המצב הנוכחי — לא ניחוש
    Task<TweakResult> ApplyAsync(CancellationToken ct);
    Task<TweakResult> RevertAsync(CancellationToken ct);
}

// Safety/RegistryTweak.cs
public abstract class RegistryTweak : ITweak
{
    protected abstract RegistryKey Root { get; }
    protected abstract string SubKey  { get; }
    protected abstract string Name    { get; }
    protected abstract object Desired { get; }

    public async Task<TweakResult> ApplyAsync(CancellationToken ct)
    {
        if (!IsSupported(SystemInfo.Current))
            return TweakResult.Unsupported($"{Id}: לא נתמך במכשיר/בגרסה הזו");

        // 1) לתפוס את הערך המקורי פעם אחת בלבד — לעולם לא לדרוס גיבוי קיים
        var backup = await BackupStore.CaptureOnceAsync(Id, Root, SubKey, Name, ct);

        // 2) נקודת שחזור מערכת רק לשינויים רגישים (יקר — לא לכל מתג)
        if (Sensitivity == TweakSensitivity.High)
            await SystemRestore.CreateAsync($"MyShell: {Id}", ct);

        try
        {
            using var key = Root.CreateSubKey(SubKey, writable: true)
                            ?? throw new InvalidOperationException("אין הרשאת כתיבה");
            key.SetValue(Name, Desired);

            // 3) אימות אחרי כתיבה — ה-API החזיר הצלחה ≠ הערך באמת השתנה
            var actual = key.GetValue(Name);
            if (!Equals(actual, Desired))
            {
                await RevertAsync(ct);
                return TweakResult.Failed($"{Id}: אימות נכשל (נקרא {actual})");
            }
            await StateStore.MarkAppliedAsync(Id, backup, ct);
            return TweakResult.Ok(RequiresRestart);
        }
        catch (Exception ex)
        {
            await RevertAsync(ct);                       // rollback על כל חריגה
            return TweakResult.Failed($"{Id}: {ex.Message}");
        }
    }

    public async Task<TweakResult> RevertAsync(CancellationToken ct)
    {
        var backup = await BackupStore.LoadAsync(Id, ct);
        if (backup is null) return TweakResult.Ok();     // מעולם לא הוחל — no-op

        using var key = Root.CreateSubKey(SubKey, writable: true);
        if (backup.Existed) key.SetValue(Name, backup.Value!);
        else                key.DeleteValue(Name, throwOnMissingValue: false);

        await StateStore.ClearAsync(Id, ct);             // הגיבוי נשמר לאבחון
        return TweakResult.Ok(RequiresRestart);
    }
}
```

**שלושה כללים שמוסקים ישירות מ-Winhanced:**
1. `CaptureOnceAsync` — **לעולם לא לדרוס גיבוי קיים** (אחרת Apply שני מגבה את הערך שלנו).
2. אימות-אחרי-כתיבה חובה — ה-API יכול להחזיר הצלחה בלי שהערך השתנה.
3. `IsSupported` **לפני** הכול — כשלון נקי עדיף על כתיבה עיוורת.

---

## 6. סיכום מנהלים

**מה Winhanced באמת עושה:** היא לא "אופטימייזר Registry". היא **Shell של המערכת** שנרשם דרך
יכולת `gamingHome` הרשמית של Windows, מנהל **צי Backends פר-יצרן** לשליטת TDP/מאווררים
(PawnIO · MSR · SMU · ACPI · WMI · EC), מריץ **בקר סגור-לולאה** שנעול על frametime מ-RTSS עם
טלמטריה כווטו-בלבד, ומציג הכול ב-WinUI 3 עם שיידרי D2D1 — כשה-HUD הוא **ווידג'ט Xbox Game Bar
רשמי, לא הזרקה**.

**מה הכי מרשים בה, הנדסית:** לא ה-UI. **משמעת האימות.** ארבע דרגות אישור כתיבה, השוואת הספק
נמדד מול מבוקש, זהות טרנזקציה עם epoch/revision/lease, שעון מונוטוני משותף, ו-fail-open מכוון
כדי שטלמטריה לא תהפוך לרצפה נסתרת. זה קוד של מישהו שנשרף בעבר מכתיבות חומרה שקטות שנכשלו.

**מה לא ניתן לחלץ ולמה:** האלגוריתמים ומחרוזות הריצה (נתיבי Registry, שאילתות WMI, שורות פקודה)
מוצפנים ב-Protector עם JIT hook. **לא ניסיתי לעקוף אותו ולא אנסה** — זו גם מגבלה משפטית וגם
מיותרת: התיעוד הרשמי (`DynamicTDP.xml`), מבנה ה-Backends, ה-Enums, ה-Attributes וה-XBF נתנו
תמונה שלמה יותר ממה שפענוח היה נותן.

**מה מותר לקחת:** ארכיטקטורה, IA, דפוסי UX, ורעיונות — הכול מותר. **אסור** להעתיק את הנכסים
שלהם (XAML מקומפל, "Living Glass", אייקוני בקר), את מאגר ה-Smart Profiles, ואת מימוש ה-Smart
Launch Watcher. הכלים שבהם הם משתמשים (RTSS · Sunshine · RyzenAdj · LibreHardwareMonitor ·
PawnIO · Discord RPC) פתוחים וזמינים לנו באותה מידה — בדיוק כפי שנקבע ב-`winhanced_servers_report.md`.

---

### נספח — הכלים שנוצרו לניתוח (כולם ב-`C:\tmp`, קריאה בלבד)

| כלי | תפקיד |
|---|---|
| `dump_xbf_pristine.py` | פענוח XBF מהגיבוי הנקי (מונע זיהום מתיקון Track A) |
| `dump097.py` | פענוח 99 XBF מגרסה 0.9.9.7 |
| `probe_strings.py` | **מדידת גבול ההצפנה** — 27 מחרוזות × 2 קידודים × 2 גרסאות |
| `scan2.py` | מלאי P/Invoke + טבלת GUID של COM |
| `whsrc/` · `whshared/` · `whhw/` · `whtdp/` | 1,351 + 130 + 130 + N קבצי `.cs` מפורקים |
| `wh097/` | חילוץ סלקטיבי מהמתקין 0.9.9.7 |

**הותקן: כלום. שונה: כלום. המתקין 0.9.9.7 לא הורץ.**
