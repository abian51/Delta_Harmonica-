from __future__ import annotations

import tempfile
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable

from .harmonica_mapping import MappingProfile
from .library import data_dir
from .models import Action, Note
from .preview_audio import PreviewTone, clip_tones, scale_preview, synthesize_preview, tones_from_timeline
from .timeline import clip_actions


class RangeTimeline(tk.Canvas):
    """A progress bar with two draggable trim handles."""

    def __init__(self, parent: tk.Misc, on_change: Callable[[int, int], None]):
        super().__init__(parent, height=48, bg="#f5f7fa", highlightthickness=0, cursor="hand2")
        self.on_change = on_change
        self.duration_ms = 1
        self.start_ms = 0
        self.end_ms = 1
        self.playhead_ms = 0
        self._dragging: str | None = None
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)

    def set_range(self, duration_ms: int, start_ms: int, end_ms: int) -> None:
        self.duration_ms = max(1, duration_ms)
        self.start_ms = max(0, min(start_ms, self.duration_ms - 1))
        self.end_ms = max(self.start_ms + 1, min(end_ms, self.duration_ms))
        self.playhead_ms = self.start_ms
        self._draw()

    def set_playhead(self, time_ms: int) -> None:
        self.playhead_ms = max(0, min(time_ms, self.duration_ms))
        self._draw()

    def _position(self, time_ms: int) -> float:
        width = max(1, self.winfo_width() - 28)
        return 14 + width * time_ms / self.duration_ms

    def _time(self, x: float) -> int:
        width = max(1, self.winfo_width() - 28)
        return round(max(0, min(1, (x - 14) / width)) * self.duration_ms)

    def _draw(self) -> None:
        self.delete("all")
        left, right = self._position(0), self._position(self.duration_ms)
        start, end = self._position(self.start_ms), self._position(self.end_ms)
        self.create_rectangle(left, 18, right, 30, fill="#d7e0e9", outline="")
        self.create_rectangle(start, 18, end, 30, fill="#83b6f3", outline="")
        for x, color in ((start, "#1c67c7"), (end, "#1c67c7")):
            self.create_rectangle(x - 5, 10, x + 5, 38, fill=color, outline="white", width=2)
        self.create_line(self._position(self.playhead_ms), 8,
                         self._position(self.playhead_ms), 40, fill="#e36a32", width=2)

    def _press(self, event: tk.Event) -> None:
        start_x, end_x = self._position(self.start_ms), self._position(self.end_ms)
        self._dragging = "start" if abs(event.x - start_x) <= abs(event.x - end_x) else "end"
        self._drag(event)

    def _drag(self, event: tk.Event) -> None:
        if self._dragging is None:
            return
        point = self._time(event.x)
        if self._dragging == "start":
            self.start_ms = max(0, min(point, self.end_ms - 1))
        else:
            self.end_ms = min(self.duration_ms, max(point, self.start_ms + 1))
        self.playhead_ms = self.start_ms
        self._draw()

    def _release(self, _event: tk.Event) -> None:
        if self._dragging is not None:
            self._dragging = None
            self.on_change(self.start_ms, self.end_ms)


class PreviewWindow(tk.Toplevel):
    """Read-only synchronized audio/keyboard/harmonica preview."""

    def __init__(self, parent: tk.Misc, profile: MappingProfile,
                 notes: list[Note], actions: list[Action], base_speed: float,
                 on_speed_change: Callable[[float], tuple[list[Note], list[Action]]] | None = None,
                 clip_start_source_ms: float = 0, clip_end_source_ms: float | None = None,
                 on_range_change: Callable[[float, float | None], None] | None = None):
        super().__init__(parent)
        self.title("口琴与键盘试听预览")
        self.geometry("840x540")
        self.minsize(680, 500)
        self.profile = profile
        self.original_actions = actions
        self.original_tones = tones_from_timeline(notes, actions)
        self.base_speed = base_speed
        self.on_speed_change = on_speed_change
        self.on_range_change = on_range_change
        self.clip_start_source_ms = clip_start_source_ms
        self.clip_end_source_ms = clip_end_source_ms
        self.actions: list[Action] = []
        self.tones: list[PreviewTone] = []
        self._active_keys: set[str] = set()
        self._active_mouse: set[int] = set()
        self._cursor = 0
        self._duration = 0
        self._range_start_ms = 0
        self._full_duration = max((action.time_ms for action in actions), default=0)
        self._started_at = 0.0
        self._tick_id: str | None = None
        self._generation = 0
        self._pending_jobs = 0
        self._closed = False
        self._playing = False
        self._current_wave: Path | None = None
        self._tmpdir = tempfile.TemporaryDirectory(prefix="preview-", dir=data_dir())
        self._build()
        self._sync_range_from_source()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self) -> None:
        shell = ttk.Frame(self, padding=18)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="口琴 · 键盘同步预览", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(shell, text="播放合成示意音；仅显示动作，不会操作游戏、键盘或外设。",
                  foreground="#526171").pack(anchor="w", pady=(3, 15))

        controls = ttk.Frame(shell)
        controls.pack(fill="x")
        self.play_button = ttk.Button(controls, text="▶ 播放", command=self.play)
        self.play_button.pack(side="left")
        ttk.Button(controls, text="■ 停止", command=self.stop).pack(side="left", padx=(8, 20))
        ttk.Label(controls, text="试听／导出倍速").pack(side="left")
        self.speed_choice = tk.StringVar(value=f"{self.base_speed:g}x")
        values = sorted({0.1, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0, self.base_speed})
        speed_box = ttk.Combobox(controls, textvariable=self.speed_choice,
                                 values=tuple(f"{speed:g}x" for speed in values),
                                 state="readonly", width=8)
        speed_box.pack(side="left", padx=8)
        speed_box.bind("<<ComboboxSelected>>", lambda _event: self._speed_changed())
        ttk.Label(controls, text="同步到导出；播放时切换会从头开始", foreground="#6a7480").pack(side="left", padx=8)

        ttk.Label(shell, text="拖动蓝色两端选择导出片段；橙线表示试听位置。",
                  foreground="#526171").pack(anchor="w", pady=(15, 3))
        self.timeline = RangeTimeline(shell, self._range_changed)
        self.timeline.pack(fill="x")
        range_row = ttk.Frame(shell)
        range_row.pack(fill="x", pady=(2, 14))
        self.range_text = ttk.Label(range_row, text="截取：全曲")
        self.range_text.pack(side="left")
        ttk.Button(range_row, text="恢复全曲", command=self.reset_range).pack(side="left", padx=12)
        ttk.Label(range_row, text="起点 s").pack(side="left", padx=(10, 3))
        self.start_entry = tk.StringVar(value="0.000")
        ttk.Entry(range_row, textvariable=self.start_entry, width=8).pack(side="left")
        ttk.Label(range_row, text="终点 s").pack(side="left", padx=(10, 3))
        self.end_entry = tk.StringVar(value="0.000")
        ttk.Entry(range_row, textvariable=self.end_entry, width=8).pack(side="left")
        ttk.Button(range_row, text="应用", command=self.apply_numeric_range).pack(side="left", padx=8)
        self.clock = ttk.Label(range_row, text="00:00 / 00:00", anchor="e")
        self.clock.pack(side="right")

        self.status = ttk.Label(shell, text="准备就绪", font=("Segoe UI", 11, "bold"))
        self.status.pack(anchor="w", pady=(0, 12))

        ttk.Label(shell, text="口琴音孔", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        holes = ttk.Frame(shell)
        holes.pack(fill="x", pady=(7, 20))
        self.hole_widgets: dict[str, tk.Label] = {}
        self.hole_notes: dict[str, str] = {}
        for index, key in enumerate(self.profile.keys):
            pitch = self.profile.base + (index // 7) * 12 + (0, 2, 4, 5, 7, 9, 11)[index % 7]
            note_name = _midi_note_name(pitch)
            label = tk.Label(holes, text=f"孔 {index + 1}\n{note_name}\n{key}", width=7, height=3,
                             bg="#e8edf2", fg="#263747", relief="ridge", borderwidth=2,
                             font=("Segoe UI", 11, "bold"))
            label.pack(side="left", padx=(0, 6), expand=True, fill="x")
            self.hole_widgets[key.upper()] = label
            self.hole_notes[key.upper()] = note_name

        ttk.Label(shell, text="键盘动作", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        keyboard = ttk.Frame(shell)
        keyboard.pack(fill="x", pady=(7, 18))
        self.key_widgets: dict[str, tk.Label] = {}
        for key in self.profile.keys:
            label = tk.Label(keyboard, text=key, width=7, height=2, bg="#f5f7fa",
                             fg="#263747", relief="raised", borderwidth=2,
                             font=("Segoe UI", 11, "bold"))
            label.pack(side="left", padx=(0, 6), expand=True, fill="x")
            self.key_widgets[key.upper()] = label

        mouse_row = ttk.Frame(shell)
        mouse_row.pack(fill="x")
        ttk.Label(mouse_row, text="鼠标修饰键：").pack(side="left")
        self.mouse_widgets: dict[int, tk.Label] = {}
        for code, name in ((1, "左键"), (2, "右键"), (3, "中键")):
            label = tk.Label(mouse_row, text=name, bg="#edf0f3", fg="#56616d",
                             width=8, relief="ridge", borderwidth=1)
            label.pack(side="left", padx=(0, 8))
            self.mouse_widgets[code] = label

    def _speed_changed(self) -> None:
        restart = self._playing or self.play_button.instate(["disabled"])
        try:
            chosen_speed = float(self.speed_choice.get().removesuffix("x"))
            if self.on_speed_change is not None:
                notes, actions = self.on_speed_change(chosen_speed)
                tones = tones_from_timeline(notes, actions)
                self.original_actions = actions
                self.original_tones = tones
                self.base_speed = chosen_speed
                self._full_duration = max((action.time_ms for action in actions), default=0)
                self._sync_range_from_source()
        except Exception as exc:
            self.speed_choice.set(f"{self.base_speed:g}x")
            messagebox.showerror("无法切换倍速", str(exc), parent=self)
            return
        if restart:
            self.play()
        else:
            self.status.configure(text=f"已同步 {chosen_speed:g}x 到导出设置")

    def _sync_range_from_source(self) -> None:
        start_ms = round(self.clip_start_source_ms / self.base_speed)
        end_ms = (round(self.clip_end_source_ms / self.base_speed)
                  if self.clip_end_source_ms is not None else self._full_duration)
        self.timeline.set_range(self._full_duration, start_ms, end_ms)
        self._update_range_text()
        self._update_clock(0)

    def _update_range_text(self) -> None:
        start, end = self.timeline.start_ms, self.timeline.end_ms
        self.start_entry.set(f"{start / 1000:.3f}")
        self.end_entry.set(f"{end / 1000:.3f}")
        if start == 0 and end >= self._full_duration:
            text = "截取：全曲"
        else:
            text = f"截取：{_format_time_precise(start)} — {_format_time_precise(end)}"
        self.range_text.configure(text=text)

    def _range_changed(self, start_ms: int, end_ms: int) -> None:
        restart = self._playing or self.play_button.instate(["disabled"])
        self.stop()
        self.clip_start_source_ms = start_ms * self.base_speed
        self.clip_end_source_ms = (None if end_ms >= self._full_duration
                                   else end_ms * self.base_speed)
        if self.on_range_change is not None:
            self.on_range_change(self.clip_start_source_ms, self.clip_end_source_ms)
        self._update_range_text()
        self._update_clock(0)
        self.status.configure(text="截取范围已同步到导出设置")
        if restart:
            self.play()

    def reset_range(self) -> None:
        self.timeline.set_range(self._full_duration, 0, self._full_duration)
        self._range_changed(0, self._full_duration)

    def apply_numeric_range(self) -> None:
        try:
            start_ms = round(float(self.start_entry.get()) * 1000)
            end_ms = round(float(self.end_entry.get()) * 1000)
            if not 0 <= start_ms < end_ms <= self._full_duration:
                raise ValueError("起点和终点必须位于歌曲范围内，且终点晚于起点")
        except ValueError as exc:
            messagebox.showerror("截取范围无效", str(exc), parent=self)
            return
        self.timeline.set_range(self._full_duration, start_ms, end_ms)
        self._range_changed(start_ms, end_ms)

    def play(self) -> None:
        self.stop()
        try:
            chosen_speed = float(self.speed_choice.get().removesuffix("x"))
            ratio = chosen_speed / self.base_speed
            full_actions, full_tones = scale_preview(self.original_actions, self.original_tones, ratio)
            start_ms = round(self.timeline.start_ms / ratio)
            end_ms = round(self.timeline.end_ms / ratio)
            self.actions = clip_actions(full_actions, start_ms, end_ms)
            self.tones = clip_tones(full_tones, start_ms, end_ms)
        except ValueError as exc:
            messagebox.showerror("无法试听", str(exc), parent=self)
            return
        if not self.tones:
            self.status.configure(text="选中片段没有可试听的音符")
            return
        self._range_start_ms = start_ms
        self._duration = end_ms - start_ms
        self._update_clock(0)
        self.status.configure(text="正在准备试听音频…")
        self.play_button.configure(state="disabled")
        generation = self._generation
        output = Path(self._tmpdir.name) / f"preview-{generation}.wav"
        tones = self.tones
        duration = self._duration
        self._pending_jobs += 1

        def worker() -> None:
            error: Exception | None = None
            try:
                synthesize_preview(tones, output, duration_ms=duration)
            except Exception as exc:
                error = exc
            try:
                self.master.after(0, lambda: self._ready(generation, output, error))
            except (RuntimeError, tk.TclError):
                pass

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _ready(self, generation: int, output: Path, error: Exception | None) -> None:
        self._pending_jobs -= 1
        if self._closed:
            self._cleanup_if_idle()
            return
        if generation != self._generation:
            output.unlink(missing_ok=True)
            return
        self.play_button.configure(state="normal")
        if error:
            self.status.configure(text="试听准备失败")
            messagebox.showerror("试听失败", str(error), parent=self)
            return
        try:
            import winsound
            winsound.PlaySound(str(output), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except (ImportError, RuntimeError, OSError) as exc:
            self.status.configure(text="当前系统无法播放声音")
            messagebox.showerror("试听失败", str(exc), parent=self)
            return
        self._current_wave = output
        self._playing = True
        self._started_at = time.perf_counter()
        self.status.configure(text="播放中")
        self._tick()

    def _tick(self) -> None:
        if not self._playing:
            return
        elapsed = min(self._duration, round((time.perf_counter() - self._started_at) * 1000))
        while self._cursor < len(self.actions) and self.actions[self._cursor].time_ms <= elapsed:
            action = self.actions[self._cursor]
            if action.kind == "keyboard":
                target = self._active_keys
                item = action.label.upper()
            else:
                target = self._active_mouse
                item = action.code
            if action.down:
                target.add(item)
            else:
                target.discard(item)
            self._cursor += 1
        self._render()
        self._update_clock(elapsed)
        if elapsed >= self._duration:
            self.stop(reset=False)
            self.status.configure(text="播放完成")
        else:
            self._tick_id = self.after(16, self._tick)

    def _render(self) -> None:
        for key, widget in self.hole_widgets.items():
            active = key in self._active_keys
            widget.configure(bg="#e36a32" if active else "#e8edf2",
                             fg="white" if active else "#263747")
        for key, widget in self.key_widgets.items():
            active = key in self._active_keys
            widget.configure(bg="#2f73d9" if active else "#f5f7fa",
                             fg="white" if active else "#263747",
                             relief="sunken" if active else "raised")
        for code, widget in self.mouse_widgets.items():
            active = code in self._active_mouse
            widget.configure(bg="#2f73d9" if active else "#edf0f3",
                             fg="white" if active else "#56616d")
        if self._active_keys:
            descriptions = [f"{self.hole_notes.get(key, '?')} · 键 {key}"
                            for key in sorted(self._active_keys)]
            modifier = "（升音修饰）" if 1 in self._active_mouse else ""
            self.status.configure(text=f"正在吹奏：{' / '.join(descriptions)}{modifier}")
        elif self._playing:
            self.status.configure(text="播放中 · 休止")

    def _update_clock(self, elapsed_ms: int) -> None:
        position_ms = self.timeline.start_ms + elapsed_ms
        self.timeline.set_playhead(position_ms)
        self.clock.configure(text=f"{_format_time_precise(position_ms)} / "
                                  f"{_format_time_precise(self._full_duration)}")

    def stop(self, *, reset: bool = True) -> None:
        self._generation += 1
        if self._tick_id is not None:
            self.after_cancel(self._tick_id)
            self._tick_id = None
        if self._playing:
            try:
                import winsound
                winsound.PlaySound(None, 0)
            except (ImportError, RuntimeError, OSError):
                pass
        self._playing = False
        self._cursor = 0
        self._active_keys.clear()
        self._active_mouse.clear()
        self._render()
        self.play_button.configure(state="normal")
        if self._current_wave is not None:
            try:
                self._current_wave.unlink(missing_ok=True)
            except OSError:
                pass
            self._current_wave = None
        if reset:
            self._update_clock(0)
            self.status.configure(text="已停止")

    def close(self) -> None:
        self.stop()
        self._closed = True
        self.destroy()
        self._cleanup_if_idle()

    def _cleanup_if_idle(self) -> None:
        if self._closed and self._pending_jobs == 0:
            self._tmpdir.cleanup()


def _format_time(ms: int) -> str:
    seconds = max(0, ms // 1000)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _format_time_precise(ms: int) -> str:
    ms = max(0, ms)
    seconds, remainder = divmod(ms, 1000)
    return f"{seconds // 60:02d}:{seconds % 60:02d}.{remainder:03d}"


def _midi_note_name(pitch: int) -> str:
    names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    return f"{names[pitch % 12]}{pitch // 12 - 1}"
