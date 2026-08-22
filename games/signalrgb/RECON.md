# SignalRGB — Recon (read-only)

Target: `C:\Users\Nehoray_Cohen\AppData\Local\VortxEngine\SignalRgbLauncher.exe`
Vendor: SignalRGB (Whirlwind Virtual Realities Inc.) · **software, not a game**
(same class as VirtualDJ / Borderless Gaming).

## Install layout

```
%LOCALAPPDATA%\VortxEngine\
  SignalRgbLauncher.exe          499 KB  Squirrel stub (NOT the app)
  Update.exe                             Squirrel updater
  app-2.5.72\  app-2.5.74\               versioned installs (659 MB each)
      SignalRgbLauncher.exe      Qt launcher shell
      Signal-x64\
          SignalRgb.exe          114,334,272 B   <-- THE APP
          Qt6*.dll (Quick/QML/WebEngine/Charts/...)
          translations\qt_en.qm  (Qt framework only, not the app)
          Components\ Effects\ Plugins\ LCDFaces\ Macroscripts\
```

* Engine: **Qt 6 + QML (Qt Quick)**. The UI is native QML compiled into the
  exe as Qt resources (`qrc:/icons/...`, `qrc:/images/...`); QtWebEngine is
  present only for embedded content (effects, LCD faces, store pages).
* User data: `%APPDATA%\WhirlwindFX\SignalRgb`, `%LOCALAPPDATA%\WhirlwindFX\SignalRgb`.
* Settings: **registry** `HKCU\Software\WhirlwindFX\SignalRgb` (Qt QSettings
  NativeFormat).
* `SignalRgb.exe` is **Authenticode-signed** (Status=Valid).
* No anti-cheat, no DRM on assets. A Squirrel update replaces the whole
  `app-<ver>` folder.

## The localization system (from `Signal\UI\translation.cpp` strings)

```
:/i18n/SignalRgb_<locale>          <- QTranslator resource prefix (qrc, in-exe)
UI/Locale                          <- registry value with the chosen locale
translation / selected_locale      <- settings keys
SignalTranslation::SetCurrentLocale / FetchCurrentLocaleFromRegistry /
GetSupportedLocale / LoadNewTranslator / SetCurrentLanguage
"Failed to find supported Locale for: {}. Falling back to en"
```

Supported locale codes:
`en_US da da_DK pt es zh zh_CN zhtw zh_TW ar ms_MY ru_RU sv sv_SE sr sr_RS
sr_Cyrl_RS ja ja_JP ko ko_KR nl_NL pl pl_PL th th_TH tr tr_TR vi vi_VN`

Display names in the picker: Dansk · Français · Deutsch · Português · Español ·
中文(简体) · 中文(繁體) · **العربية** · Bahasa Melayu · Русский · Svenska ·
Srpski · 日本語 · 한국어 · Nederlands · Polski · ภาษาไทย · Türkçe · Tiếng Việt

**No Hebrew locale. Arabic (`ar`) exists and is fully translated** — that is
the RTL slot to hijack.

## What actually ships

8 `.qm` files are embedded in `SignalRgb.exe` (there is **no** `.qm` on disk
for the app, and nothing calls `QResource::registerResource` on an external
`.rcc` — the resource is the only source).

| slot (by content) | declared | offset | size | messages |
|---|---|---:|---:|---:|
| template (empty)  | –     |  99,688,303 |     270 |    6 |
| ko                | ko_KR |  99,762,415 | 194,194 | 1830 |
| **ar**            | ar_EG |  99,956,613 | **226,603** | **1813** |
| zh_CN             | zh_CN | 100,398,688 | 170,276 | 1814 |
| ms (stub)         | ms    | 100,568,968 |   8,814 |   38 |
| sr                | sr_RS | 100,872,043 | 250,378 | 1793 |
| **zh_TW**         | **ru_RU** ⚠ | 101,266,352 | 170,206 | 1793 |
| ja                | ja_JP | 101,436,562 | 189,347 | 1793 |

⚠ **The file serving Traditional Chinese declares `ru_RU` and contains ZERO
Cyrillic.** SignalRGB ships a mislabeled `.qm`. Never identify a `.qm` by its
Language block — label it by the script of its translations (`extract_corpus.py
detect_label`), or a translator gets handed a "Russian" reference column full
of Chinese. The patcher therefore locates the Arabic slot **by content** too.

There is **no Russian and no European gendered language** on disk; the
gender/context oracle is Arabic + Serbian.

## Scope

* **1,838 unique translatable strings**, 55,571 English characters.
* Median 15 chars; 1,357 ≤25 chars, 406 are 26–140, 75 are >140 (max 437).
* 264 contexts (QML file names): MainOnboardingFlow 48, ThirdpartyDevicePageInternal 44,
  Main 39, ThirdpartyInspectorTab 34, Settings 32, SettingsNavPanel 30, WindowsSettings 30…
* UI only — no subtitles, no dialogue, **no plural (numerus) forms**.
* Tokens to preserve: `%1..%9` (42 in 36 strings), literal `%` (11), `\n` (26 in
  17 strings), 2 HTML tags. No `{...}` placeholders.

## Reference languages available for every key (New-Era panel)

ko 1824/1838 · zh_CN 1806 · **ar 1801** · sr 1787 · zh_TW 1787 · ja 1787 · ms 32.

⚠ The vendor's translations are machine-made and sometimes plainly wrong —
`Sign Out → انقر فوق` ("click on"), `Decline → انخفاض` ("a decrease"),
`Macros → ماكرون` (Macron, the surname). Use them as a **context/gender
oracle with cross-language consensus**, never as gospel.

## Not translatable from the client

`catalog_en.json` (367 effects) is fetched from the server with the language
in the filename — effect names/descriptions in the store come down already
localized (or English). A client-side mod cannot change those.

## מסמכים קשורים
- באותה תיקייה: [[games/signalrgb/FEASIBILITY|FEASIBILITY]], [[games/signalrgb/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#signalrgb|CLAUDE_INDEX_games]]
