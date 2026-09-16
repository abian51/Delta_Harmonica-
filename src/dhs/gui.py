from __future__ import annotations

import json
import re
import threading
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .audio_transcription import transcribe_audio
from .converter import DEFAULT_PROFILE, convert_midi, prepare_midi
from .desktop_event_tester import open_tester
from .gg_engine_api import create_macro
from .library import data_dir, delete_song, list_songs, save_song
from .macro_export import EXPORT_FORMATS, actions_from_file, export_macro
from .midi_import import inspect_midi
from .preview_window import PreviewWindow
from .sample_midi import create_three_note_sample


class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Delta Harmonica Studio")
        self.geometry("1040x680")
        self.minsize(900, 600)
        self.records: list[dict] = []
        self.current_record_path: str | None = None
        self.preview_window: PreviewWindow | None = None
        self._build()
        self.reload_library()

    def _build(self) -> None:
        header = ttk.Frame(self, padding=14); header.pack(fill="x")
        ttk.Label(header, text="Delta Harmonica Studio", font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Label(header, text="CONVERTER_READY · GG ENGINE API", foreground="#176b3a").pack(side="right")
        warning = ttk.Label(self, text="可通过 GG 自己的本机 Engine 接口创建未绑定宏；项目不会直接修改 GG 数据库，也不会启动游戏。",
                            padding=(14, 0, 14, 10), foreground="#176b3a")
        warning.pack(fill="x")

        body = ttk.Panedwindow(self, orient="horizontal"); body.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        left = ttk.Frame(body, padding=8); right = ttk.Frame(body, padding=12)
        body.add(left, weight=2); body.add(right, weight=5)
        toolbar = ttk.Frame(left); toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="导入 MIDI", command=self.add_files).pack(side="left")
        ttk.Button(toolbar, text="导入音频", command=self.add_audio).pack(side="left", padx=6)
        ttk.Button(toolbar, text="三音样本", command=self.add_sample).pack(side="left")
        ttk.Button(toolbar, text="删除", command=self.remove_selected).pack(side="right")
        self.song_list = tk.Listbox(left, exportselection=False)
        self.song_list.pack(fill="both", expand=True); self.song_list.bind("<<ListboxSelect>>", self.select_song)
        ttk.Label(left, text="曲库保存在用户本地数据目录，不放入项目或 Git。", wraplength=280,
                  foreground="#555").pack(fill="x", pady=(8, 0))

        self.name = tk.StringVar(); self.path = tk.StringVar(); self.polyphony = tk.StringVar(value="reject")
        self.transpose = tk.IntVar(value=0); self.speed = tk.DoubleVar(value=1.0)
        self.min_hold = tk.IntVar(value=35); self.safe_gap = tk.IntVar(value=5)
        self.clip_start_source_ms = 0.0
        self.clip_end_source_ms: float | None = None
        self.clip_text = tk.StringVar(value="全曲")
        self.export_format = tk.StringVar(value=next(iter(EXPORT_FORMATS.values()))["label"])
        form = ttk.Frame(right); form.pack(fill="x")
        self._row(form, 0, "歌曲名称", ttk.Entry(form, textvariable=self.name))
        path_entry = ttk.Entry(form, textvariable=self.path, state="readonly")
        self._row(form, 1, "MIDI 文件", path_entry)
        ttk.Label(form, text="轨道（可多选；不选表示全部）").grid(row=2, column=0, sticky="nw", pady=6)
        self.tracks = tk.Listbox(form, selectmode="extended", height=6, exportselection=False)
        self.tracks.grid(row=2, column=1, sticky="ew", pady=6)
        self._row(form, 3, "多声部策略", ttk.Combobox(form, textvariable=self.polyphony,
                                                       values=("reject", "highest", "lowest"), state="readonly"))
        numbers = ttk.Frame(form)
        for index, (label, variable, start, end, increment) in enumerate([
            ("移调", self.transpose, -36, 36, 1),
            ("最短按键 ms", self.min_hold, 1, 1000, 1), ("安全间隔 ms", self.safe_gap, 0, 500, 1),
        ]):
            box = ttk.Frame(numbers); box.grid(row=0, column=index, padx=(0, 12), sticky="ew")
            ttk.Label(box, text=label).pack(anchor="w")
            ttk.Spinbox(box, textvariable=variable, from_=start, to=end, increment=increment, width=12).pack(anchor="w")
        speed_box = ttk.Frame(numbers); speed_box.grid(row=0, column=3, padx=(0, 12), sticky="ew")
        ttk.Label(speed_box, text="导出倍速").pack(anchor="w")
        ttk.Combobox(speed_box, textvariable=self.speed, state="readonly", width=10,
                     values=(0.1, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0)).pack(anchor="w")
        self._row(form, 4, "转换设置", numbers)
        clip_row = ttk.Frame(form)
        ttk.Label(clip_row, textvariable=self.clip_text).pack(side="left")
        ttk.Button(clip_row, text="恢复全曲", command=self.reset_clip).pack(side="left", padx=12)
        self._row(form, 5, "宏截取片段", clip_row)
        form.columnconfigure(1, weight=1)

        actions = ttk.Frame(right); actions.pack(fill="x", pady=(14, 6))
        ttk.Button(actions, text="保存设置", command=self.save_current).pack(side="left")
        ttk.Button(actions, text="试听预览", command=self.preview_current).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="生成时间轴", command=self.convert_current).pack(side="left", padx=8)
        ttk.Button(actions, text="生成并创建 GG 宏", command=self.create_gg_macro).pack(side="left")
        ttk.Button(actions, text="批量转换曲库", command=self.convert_all).pack(side="left")
        export_row = ttk.Frame(right); export_row.pack(fill="x", pady=(0, 14))
        ttk.Label(export_row, text="外设格式").pack(side="left")
        ttk.Combobox(export_row, textvariable=self.export_format,
                     values=tuple(item["label"] for item in EXPORT_FORMATS.values()),
                     state="readonly", width=31).pack(side="left", padx=8)
        ttk.Button(export_row, text="导出外设宏", command=self.export_device_macro).pack(side="left")
        ttk.Button(export_row, text="打开桌面事件检测", command=lambda: open_tester(self)).pack(side="right")
        ttk.Separator(right).pack(fill="x", pady=(0, 12))
        ttk.Label(right, text="状态与转换报告", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.log = tk.Text(right, height=14, wrap="word", state="disabled", background="#f7f7f7")
        self.log.pack(fill="both", expand=True, pady=(6, 0))
        self.write_log("界面已就绪。可导入 MIDI，或把单旋律 MP3/音频自动识别为 MIDI。")

    @staticmethod
    def _row(parent: ttk.Frame, row: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
        widget.grid(row=row, column=1, sticky="ew", pady=6)

    def write_log(self, text: str) -> None:
        self.log.configure(state="normal"); self.log.insert("end", text + "\n"); self.log.see("end")
        self.log.configure(state="disabled")

    def reload_library(self, select_name: str | None = None) -> None:
        self.records = list_songs(); self.song_list.delete(0, "end")
        selected = None
        for index, record in enumerate(self.records):
            self.song_list.insert("end", record.get("name", Path(record.get("midi_path", "未知")).stem))
            if select_name and record.get("name") == select_name: selected = index
        if selected is not None:
            self.song_list.selection_set(selected); self.song_list.event_generate("<<ListboxSelect>>")

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(parent=self, title="导入 MIDI",
                                            filetypes=[("MIDI", "*.mid *.midi")])
        for raw in paths:
            path = Path(raw)
            record = self.default_record(path)
            try:
                inspect_midi(path); save_song(record["name"], record)
            except Exception as exc:
                messagebox.showerror("无法导入", f"{path.name}\n{exc}", parent=self)
        if paths:
            self.reload_library(Path(paths[-1]).stem)
            self.write_log(f"已导入 {len(paths)} 个文件。")

    def add_audio(self) -> None:
        raw = filedialog.askopenfilename(
            parent=self, title="导入音频并识别为 MIDI",
            filetypes=[("音频", "*.mp3 *.wav *.flac *.ogg"), ("所有文件", "*.*")],
        )
        if not raw:
            return
        source = Path(raw)
        safe_stem = re.sub(r"[^\w.-]+", "_", source.stem, flags=re.UNICODE).strip("._") or "audio"
        output = data_dir() / "samples" / f"{safe_stem}_{uuid.uuid4().hex[:8]}_transcribed.mid"
        self.write_log(f"正在识别音频：{source.name}（较长音频可能需要一些时间）")

        def worker() -> None:
            try:
                report = transcribe_audio(source, output)
            except Exception as exc:
                self.after(0, lambda error=exc: self._audio_failed(error))
                return
            self.after(0, lambda: self._audio_finished(source.stem, output, report))

        threading.Thread(target=worker, daemon=True).start()

    def _audio_failed(self, error: Exception) -> None:
        self.write_log(f"音频识别失败：{error}")
        messagebox.showerror("音频识别失败", str(error), parent=self)

    def _audio_finished(self, source_name: str, midi_path: Path, report: dict) -> None:
        record = self.default_record(midi_path)
        record["name"] = source_name
        save_song(record["name"], record)
        self.reload_library(record["name"])
        self.write_log(json.dumps(report, ensure_ascii=False, indent=2))
        messagebox.showinfo("音频识别完成",
                            f"已识别 {report['notes']} 个音符并加入曲库。\n\n自动结果适合单旋律，建议先试听或检查。",
                            parent=self)

    def add_sample(self) -> None:
        path = create_three_note_sample(data_dir() / "samples" / "desktop_acceptance_C_D_E.mid")
        record = self.default_record(path); record["name"] = "桌面验收三音 C-D-E"
        save_song(record["name"], record); self.reload_library(record["name"])
        self.write_log(f"已生成三音样本：{path}")

    @staticmethod
    def default_record(path: Path) -> dict:
        return {"name": path.stem, "midi_path": str(path.resolve()), "tracks": [], "polyphony": "reject",
                "transpose": 0, "speed": 1.0, "min_hold_ms": 35, "safe_gap_ms": 5,
                "clip_start_source_ms": 0.0, "clip_end_source_ms": None}

    def select_song(self, _event=None) -> None:
        selection = self.song_list.curselection()
        if not selection: return
        if self.preview_window is not None and self.preview_window.winfo_exists():
            self.preview_window.close()
            self.preview_window = None
        record = self.records[selection[0]]; self.current_record_path = record.get("_record_path")
        self.name.set(record.get("name", "")); self.path.set(record.get("midi_path", ""))
        self.polyphony.set(record.get("polyphony", "reject")); self.transpose.set(record.get("transpose", 0))
        self.speed.set(record.get("speed", 1.0)); self.min_hold.set(record.get("min_hold_ms", 35))
        self.safe_gap.set(record.get("safe_gap_ms", 5)); self.tracks.delete(0, "end")
        self.set_clip(record.get("clip_start_source_ms", 0), record.get("clip_end_source_ms"))
        try:
            selected_tracks = set(record.get("tracks", []))
            for index, track in enumerate(inspect_midi(self.path.get())):
                self.tracks.insert("end", f"{track['index']}: {track['name']}（{track['notes']} 音符）")
                if track["index"] in selected_tracks: self.tracks.selection_set(index)
        except Exception as exc:
            self.write_log(f"读取失败：{exc}")

    def form_record(self) -> dict:
        return {"name": self.name.get().strip(), "midi_path": self.path.get(),
                "tracks": list(self.tracks.curselection()), "polyphony": self.polyphony.get(),
                "transpose": self.transpose.get(), "speed": self.speed.get(),
                "min_hold_ms": self.min_hold.get(), "safe_gap_ms": self.safe_gap.get(),
                "clip_start_source_ms": self.clip_start_source_ms,
                "clip_end_source_ms": self.clip_end_source_ms}

    def set_clip(self, start_source_ms: float, end_source_ms: float | None) -> None:
        self.clip_start_source_ms = float(start_source_ms)
        self.clip_end_source_ms = float(end_source_ms) if end_source_ms is not None else None
        if self.clip_start_source_ms == 0 and self.clip_end_source_ms is None:
            self.clip_text.set("全曲")
        else:
            end = "结尾" if self.clip_end_source_ms is None else f"{self.clip_end_source_ms / 1000:.2f} 秒"
            self.clip_text.set(f"{self.clip_start_source_ms / 1000:.2f} 秒 — {end}（原曲时间）")

    def reset_clip(self) -> None:
        if self.preview_window is not None and self.preview_window.winfo_exists():
            self.preview_window.reset_range()
        else:
            self.set_clip(0, None)

    def save_current(self) -> dict | None:
        if not self.path.get(): messagebox.showinfo("尚未选择", "请先导入或选择一首 MIDI。", parent=self); return None
        try:
            record = self.form_record(); new_path = save_song(record["name"], record)
            if self.current_record_path and Path(self.current_record_path) != new_path:
                delete_song(self.current_record_path)
            self.current_record_path = str(new_path); self.reload_library(record["name"])
            self.write_log(f"已保存设置：{record['name']}")
            return record
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc), parent=self); return None

    def convert_record(self, record: dict) -> dict:
        output = data_dir() / "exports" / Path(record["_record_path"] if "_record_path" in record else record["name"]).stem
        tracks = set(record.get("tracks", [])) or None
        clip_end = record.get("clip_end_source_ms")
        return convert_midi(record["midi_path"], output, profile_path=DEFAULT_PROFILE, tracks=tracks,
                            polyphony=record.get("polyphony", "reject"), transpose=int(record.get("transpose", 0)),
                            speed=float(record.get("speed", 1.0)), min_hold_ms=int(record.get("min_hold_ms", 35)),
                            safe_gap_ms=int(record.get("safe_gap_ms", 5)),
                            clip_start_source_ms=float(record.get("clip_start_source_ms", 0)),
                            clip_end_source_ms=float(clip_end) if clip_end is not None else None)

    def convert_current(self) -> None:
        record = self.save_current()
        if not record: return
        try:
            report = self.convert_record(record); self.write_log(json.dumps(report, ensure_ascii=False, indent=2))
            messagebox.showinfo("转换完成", f"已生成 {report['notes']} 个音符、{report['actions']} 个动作。", parent=self)
        except Exception as exc:
            messagebox.showerror("转换失败", str(exc), parent=self); self.write_log(f"转换失败：{exc}")

    def preview_current(self) -> None:
        if not self.path.get():
            messagebox.showinfo("尚未选择", "请先导入或选择一首 MIDI。", parent=self)
            return
        try:
            if self.preview_window is not None and self.preview_window.winfo_exists():
                self.preview_window.close()
            record = self.form_record()
            profile, notes, actions = prepare_midi(
                record["midi_path"], profile_path=DEFAULT_PROFILE,
                tracks=set(record["tracks"]) or None,
                polyphony=record["polyphony"], transpose=int(record["transpose"]),
                speed=float(record["speed"]), min_hold_ms=int(record["min_hold_ms"]),
                safe_gap_ms=int(record["safe_gap_ms"]),
            )
            if not notes:
                raise ValueError("当前 MIDI 没有可试听的音符")
            def update_preview_speed(chosen_speed: float):
                updated = dict(record, speed=chosen_speed)
                _, updated_notes, updated_actions = prepare_midi(
                    updated["midi_path"], profile_path=DEFAULT_PROFILE,
                    tracks=set(updated["tracks"]) or None,
                    polyphony=updated["polyphony"], transpose=int(updated["transpose"]),
                    speed=chosen_speed, min_hold_ms=int(updated["min_hold_ms"]),
                    safe_gap_ms=int(updated["safe_gap_ms"]),
                )
                self.speed.set(chosen_speed)
                return updated_notes, updated_actions

            self.preview_window = PreviewWindow(
                self, profile, notes, actions, float(record["speed"]),
                on_speed_change=update_preview_speed,
                clip_start_source_ms=float(record.get("clip_start_source_ms", 0)),
                clip_end_source_ms=record.get("clip_end_source_ms"),
                on_range_change=self.set_clip,
            )
            self.write_log(f"已打开试听预览：{record['name']}（{len(notes)} 个音符）")
        except Exception as exc:
            messagebox.showerror("无法试听", str(exc), parent=self)
            self.write_log(f"试听准备失败：{exc}")

    def create_gg_macro(self) -> None:
        record = self.save_current()
        if not record:
            return
        macro_name = f"DHS_{record['name']}"
        if not messagebox.askyesno(
            "创建 GG 宏",
            f"将在 SteelSeries GG 中创建一个未绑定宏：\n{macro_name}\n\n不会修改任何现有宏或按键绑定。是否继续？",
            parent=self,
        ):
            return
        try:
            report = self.convert_record(record)
            events = json.loads(Path(report["gg_api_events_file"]).read_text(encoding="utf-8"))
            macro_id = create_macro(macro_name, events)
            self.write_log(f"GG 宏已创建：{macro_name}（{macro_id}）")
            messagebox.showinfo(
                "GG 宏已创建",
                f"已通过 GG Engine 创建：\n{macro_name}\n\n现在可在 GG 的宏编辑器中查看并手动绑定。",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror("创建失败", str(exc), parent=self)
            self.write_log(f"GG 宏创建失败：{exc}")

    def export_device_macro(self) -> None:
        record = self.save_current()
        if not record:
            return
        label = self.export_format.get()
        format_id = next((key for key, item in EXPORT_FORMATS.items() if item["label"] == label), None)
        if not format_id:
            messagebox.showerror("导出失败", "请选择有效的外设格式。", parent=self)
            return
        extension = EXPORT_FORMATS[format_id]["extension"]
        safe_name = re.sub(r'[<>:"/\\|?*]+', "_", record["name"]).strip(" .") or "macro"
        output = filedialog.asksaveasfilename(
            parent=self, title=f"导出 {label}", defaultextension=extension,
            initialfile=f"DHS_{safe_name}{extension}",
            filetypes=[(label, f"*{extension}"), ("所有文件", "*.*")],
        )
        if not output:
            return
        try:
            conversion = self.convert_record(record)
            actions = actions_from_file(conversion["timeline_file"])
            report = export_macro(actions, f"DHS_{record['name']}", format_id, output)
            self.write_log(json.dumps(report, ensure_ascii=False, indent=2))
            note = ""
            if format_id == "razer_synapse3_xml":
                note = "\n\n此文件用于 Synapse 3；Synapse 4 与其格式不兼容。"
            elif format_id == "autohotkey_v2":
                note = "\n\n安装 AutoHotkey v2 后双击脚本，按 F8 播放。"
            elif format_id == "logitech_lua":
                note = "\n\n请把内容粘贴到 G HUB 脚本编辑器，默认按 G6 播放。"
            messagebox.showinfo("导出完成", f"已导出：\n{report['file']}{note}", parent=self)
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc), parent=self)
            self.write_log(f"外设宏导出失败：{exc}")

    def convert_all(self) -> None:
        success = 0; failures = []
        for record in list_songs():
            try: self.convert_record(record); success += 1
            except Exception as exc: failures.append(f"{record.get('name', '未知')}: {exc}")
        self.write_log(f"批量转换完成：成功 {success}，失败 {len(failures)}。")
        for failure in failures: self.write_log("  " + failure)
        messagebox.showinfo("批量转换", f"成功 {success} 首，失败 {len(failures)} 首。", parent=self)

    def remove_selected(self) -> None:
        selection = self.song_list.curselection()
        if not selection: return
        record = self.records[selection[0]]
        if messagebox.askyesno("删除曲库记录", f"只删除曲库记录，不删除原 MIDI：\n{record.get('name')}", parent=self):
            delete_song(record["_record_path"]); self.reload_library(); self.write_log("已删除曲库记录，原 MIDI 保留。")


def run_gui() -> None:
    Studio().mainloop()
