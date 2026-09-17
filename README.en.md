# Delta Harmonica Studio

[简体中文](README.md) | [English](README.en.md)

Delta Harmonica Studio is a Windows desktop app that turns MIDI or monophonic audio into a reviewable keyboard/mouse timeline. It can create an unbound SteelSeries GG macro or export files for Razer Synapse 3, Logitech G HUB, AutoHotkey v2, and other tools.

The app itself does not launch a game, access a game process, send live keystrokes, or edit GG's SQLite database. It asks for confirmation before creating a GG macro, which you must then bind manually in GG. An exported AutoHotkey script sends input only if you choose to run it.

## Features

- Import MIDI files and inspect or select tracks
- Transcribe a clear monophonic melody from MP3, WAV, FLAC, or OGG to MIDI
- Reject polyphonic passages or reduce them to their highest or lowest note
- Use the harmonica's octave-down (left mouse), semitone-up (middle mouse), and octave-up (right mouse) controls; optionally fold out-of-range notes by octaves
- Adjust transposition, speed, minimum key-hold time, and safe gaps
- Preview synthesized audio with animated harmonica holes, keyboard keys, and mouse modifiers
- Select a segment by dragging both ends of the preview timeline or entering exact times; use the same segment and speed for exports
- Optionally vary whole-note timing by 0–15 ms where there is enough free space, without changing key-hold duration
- Configure harmonica key mapping in JSON and manage a local song library
- Export a JSON timeline, CSV event list, and GG API events
- Create an unbound macro through the local SteelSeries GG Engine interface
- Export Razer Synapse 3 XML, Logitech G HUB Lua, AutoHotkey v2, or generic JSON
- Inspect desktop keyboard and mouse events in a separate test window

## Requirements

- Windows 10 or 11
- Python 3.11 or newer
- SteelSeries GG running locally, only if you want to create a GG macro

The GG Engine integration was checked with SteelSeries GG 119. This is not a stable third-party API published by SteelSeries, so it may need revalidation after a GG update.

## Install

Open PowerShell in the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[audio,dev]"
.\.venv\Scripts\python.exe -m pytest
```

If `py` cannot find your installed Python, use the full path to its executable for the first command. The `audio` extra installs the audio-to-MIDI dependencies; `dev` installs the test runner.

## Start

Double-click `启动_Delta_Harmonica.bat` in the project root, or run:

```powershell
.\.venv\Scripts\python.exe -m dhs
```

## Desktop workflow

1. Click “导入 MIDI” (Import MIDI), “导入音频” (Import Audio), or “三音样本” (Three-note sample).
2. Select a song and tracks, then choose the polyphony policy, transposition, export speed, and other settings. “随机微调 ms” (Random Timing Variation) defaults to 15; set it to 0 to disable it.
   If the MIDI still contains unplayable notes, set “超音域处理” (Out-of-range handling) to `octave_fold`. This shifts only unplayable notes by whole octaves, changing their actual pitch. The default `reject` never silently changes the score.
3. Click “试听预览” (Preview). The window plays a synthesized guide tone and highlights harmonica holes, keyboard keys, and mouse modifiers. Drag the two blue timeline handles to select a segment, or enter its start/end times in seconds and click “应用” (Apply). The preview speed and selected segment sync to the main window and are used by all subsequent exports. “恢复全曲” (Full song) clears the trim.
4. Click “生成时间轴” (Generate Timeline) to write reviewable files without creating a device macro.
5. Click “生成并创建 GG 宏” (Generate and Create GG Macro) to confirm and create an unbound macro. Find the new `DHS_` macro in GG and bind it manually.
6. For another device, choose a format under “外设格式” (Device Format) and click “导出外设宏” (Export Device Macro).

Creating a GG macro does not overwrite an existing macro or change a device binding. The preview uses MIDI-based synthesized audio—not the original MP3 or the game's harmonica sound—and never sends keystrokes. Preview playback is limited to 10 minutes; longer songs can still be converted and exported.

Timing variation affects exported files only; the preview plays the unmodified reference rhythm. Each note's modifiers, key-down, and key-up move together, preserving its hold duration. When a gap is too short, the variation is reduced or skipped. This does not guarantee avoidance of any detection system; follow the target software's rules.

### Device formats

- **Razer Synapse 3 XML:** Import the XML in Synapse 3's Macro module, then assign the macro to a device button. Synapse 3 and Synapse 4 macro files are incompatible; Synapse 4 is not supported by this exporter.
- **Logitech G HUB Lua:** Paste the exported Lua into a G HUB scripting editor. Mouse button 6 (G6) is the default trigger; edit `TRIGGER_BUTTON` near the top of the file to change it.
- **Dareu “Muma Ren” / other devices (AutoHotkey v2):** Install AutoHotkey v2, run the exported `.ahk` script, and press F8 to play it. This is a generic workaround, not a file that imports into a Dareu driver: the “Muma Ren” product line has no reliable, publicly documented universal macro import format.
- **Generic JSON:** Preserves the millisecond timeline and HID key codes for conversion by another application.

Device software may change its import behavior. Test with the built-in three-note sample before relying on an exported macro. Exporting a script does not install or launch third-party software.

### Audio-to-MIDI limitations

Transcription uses pYIN fundamental-frequency tracking. It works best for a clear **single melody**, such as harmonica, humming, or a solo instrument. Drums, chords, and multiple voices in a mixed song can reduce accuracy; review the resulting MIDI before exporting. Audio analysis runs locally and does not upload your files.

## Command line

Inspect MIDI tracks:

```powershell
.\.venv\Scripts\python.exe -m dhs inspect .\song.mid
```

Convert MIDI to a timeline:

```powershell
.\.venv\Scripts\python.exe -m dhs convert .\song.mid --output .\output\song
```

Common options:

- `--track N`: Select a track; repeat for multiple tracks
- `--polyphony reject|highest|lowest`: Polyphony handling
- `--out-of-range reject|octave_fold`: Out-of-range handling; defaults to rejection
- `--transpose N`: Transpose by semitones
- `--speed N`: Playback/export speed multiplier
- `--min-hold N`: Minimum key-hold duration in milliseconds
- `--safe-gap N`: Minimum gap between actions in milliseconds
- `--clip-start N` and `--clip-end N`: Optional segment boundaries in milliseconds of the original MIDI
- `--timing-variation N`: Optional random timing variation of 0–15 ms for exports; the CLI default is 0

List GG macros without changing them:

```powershell
.\.venv\Scripts\python.exe -m dhs gg-list
```

Create an unbound GG macro from an already generated API event file:

```powershell
.\.venv\Scripts\python.exe -m dhs gg-create .\output\song\gg_events.api.json --name "DHS_MySong"
```

Transcribe audio to MIDI:

```powershell
.\.venv\Scripts\python.exe -m dhs transcribe .\melody.mp3 --output .\melody.mid
```

Export a device macro from a generated timeline:

```powershell
.\.venv\Scripts\python.exe -m dhs export-macro .\output\song\timeline.json --format logitech_lua --output .\song.lua --name "DHS_MySong"
```

Available formats: `razer_synapse3_xml`, `logitech_lua`, `autohotkey_v2`, and `generic_json`.

## Generated files

Each conversion writes:

- `timeline.json`: Human-readable action timeline
- `events.csv`: Events for spreadsheet review
- `gg_events.api.json`: Events submitted to the GG Engine by this app
- `gg_events.unverified.json`: An older candidate format retained for research
- `report.json`: Parameters, counts, and warnings

`gg_events.api.json` is not a file you can double-click to import into GG; use this app's GG command or button.

## Key mapping

The example configuration is [profiles/harmonica.example.json](profiles/harmonica.example.json). The keys `Z X C V B N M ,` correspond to scale degrees `1 2 3 4 5 6 7 high-1`. Left mouse shifts the row down 12 semitones, middle mouse adds one semitone, and right mouse shifts it up 12 semitones. With the current assumed C4 base (MIDI 60), the playable range is MIDI 48–85. The mouse-control interpretation follows a [community project](https://github.com/LianZiZhou/HarmonicaScript); the absolute base pitch still needs in-game calibration.

## Safety and privacy

- The app does not directly read or write macro contents in the GG database.
- It does not create device key bindings, launch or control games, or upload MIDI, audio, library, or macro data.
- The desktop UI stores its song library and generated files in the current Windows user's local application-data directory, not in the Git repository. Command-line output goes to the path specified with `--output`.
- `.venv`, caches, build artifacts, database files, and `local-data` are excluded by `.gitignore`.

GG macro creation uses the local certificate generated by GG and connects only to the `127.0.0.1` Engine address specified in `coreProps.json`. The project does not export or commit the certificate's private key.

## Development and testing

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Code is under `src/dhs`, tests under `tests`. GG requests go through `tools/gg_engine_request.ps1`, which discovers a valid local SteelSeries certificate dynamically and contains no fixed fingerprint or personal identifier.

## Format references

- Audio analysis uses [librosa pYIN](https://librosa.org/doc/latest/generated/librosa.pyin.html); see the [librosa project](https://github.com/librosa/librosa).
- Logitech Lua calls such as `OnEvent`, `PressKey`, `ReleaseKey`, and `Sleep` follow examples in a community [G HUB Lua API cheat sheet](https://github.com/jehillert/logitech-ghub-lua-cheatsheet).
- The Razer exporter follows a [Synapse 3 XML sample on Razer Insider](https://insider.razer.com/systems-14/fn-key-other-key-customization-14869) and a [keyboard/mouse XML example on GitHub](https://gist.github.com/myl7/085db70b12a75e8973ce3ae082c1365a). [Razer's own guidance](https://dl.razerzone.com/videos/transcripts/Transcript_How%20to%20export%20and%20import%20macros%20in%20Razer%20Synapse%204.pdf) says Synapse 3 and 4 macro files are incompatible.
- The generic script follows the [AutoHotkey v2 documentation](https://www.autohotkey.com/docs/v2/).

## Verification status

- MIDI conversion: automated tests pass.
- Preview trimming and exported timelines: automated tests pass, including proper key release when trimming through a sustained note.
- Timing variation: key pairing, hold duration, and safe-gap tests pass; no anti-detection guarantee is made.
- MP3/WAV single-tone transcription: synthetic-audio tests pass; accuracy on real songs depends on the source.
- Razer, Logitech, AutoHotkey, and JSON exports: file-structure tests pass; imports into the respective vendor software and devices have not been tested here.
- GG macro creation and immediate readback: verified. Persistence after restarting GG and playback through a bound device have not yet been verified.

## License

This repository currently has no open-source license. Until a `LICENSE` file is added, all rights are reserved by default. Choose and add a license before inviting external contributions or allowing redistribution.
