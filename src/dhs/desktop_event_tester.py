"""Focused-window event verifier. This module records input and never emits it."""

from __future__ import annotations

import json
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk


STATUS = "READY"


class EventTester(tk.Toplevel):
    def __init__(self, parent: tk.Misc | None = None):
        super().__init__(parent)
        self.title("桌面事件检测（仅当前窗口）")
        self.geometry("760x480")
        self.events: list[dict] = []
        self.started = time.perf_counter()
        self.recording = False
        ttk.Label(self, text="开始后把鼠标停在事件表格区域，再手动按外设绑定键。这里只记录，不会主动发送任何输入。",
                  wraplength=720).pack(fill="x", padx=16, pady=(14, 8))
        self.status = tk.StringVar(value="尚未开始记录。")
        ttk.Label(self, textvariable=self.status).pack(fill="x", padx=16)
        columns = ("time", "source", "action", "code")
        self.table = ttk.Treeview(self, columns=columns, show="headings")
        for column, label, width in [("time", "时间(ms)", 110), ("source", "来源", 120),
                                      ("action", "动作", 120), ("code", "键/按钮", 300)]:
            self.table.heading(column, text=label); self.table.column(column, width=width)
        self.table.pack(fill="both", expand=True, padx=16, pady=10)
        buttons = ttk.Frame(self); buttons.pack(fill="x", padx=16, pady=(0, 14))
        self.record_button = ttk.Button(buttons, text="开始记录", command=self.toggle_recording)
        self.record_button.pack(side="left")
        ttk.Button(buttons, text="清空", command=self.clear).pack(side="left")
        ttk.Button(buttons, text="导出 JSON", command=self.export).pack(side="left", padx=8)
        ttk.Button(buttons, text="关闭", command=self.destroy).pack(side="right")
        self.table.focus_set()
        self.bind("<KeyPress>", lambda event: self.record("keyboard", "down", event.keysym, event.keycode))
        self.bind("<KeyRelease>", lambda event: self.record("keyboard", "up", event.keysym, event.keycode))
        for button in (1, 2, 3):
            self.table.bind(f"<ButtonPress-{button}>", lambda event, b=button: self.record("mouse", "down", f"button-{b}", b))
            self.table.bind(f"<ButtonRelease-{button}>", lambda event, b=button: self.record("mouse", "up", f"button-{b}", b))

    def record(self, source: str, action: str, label: str, code: int) -> None:
        if not self.recording:
            return
        item = {"time_ms": round((time.perf_counter() - self.started) * 1000, 3), "source": source,
                "action": action, "label": label, "code": code}
        self.events.append(item)
        self.table.insert("", "end", values=(item["time_ms"], source, action, f"{label} ({code})"))
        self.table.yview_moveto(1)
        self.status.set(f"已记录 {len(self.events)} 个事件；窗口失焦期间不会记录。")

    def toggle_recording(self) -> None:
        self.recording = not self.recording
        if self.recording:
            self.started = time.perf_counter()
            self.record_button.configure(text="停止记录")
            self.status.set("正在记录；请保持窗口聚焦、鼠标位于事件表格区域。")
            self.table.focus_set()
        else:
            self.record_button.configure(text="开始记录")
            self.status.set(f"已停止，共 {len(self.events)} 个事件。现在可以导出。")

    def clear(self) -> None:
        self.events.clear(); self.started = time.perf_counter()
        for row in self.table.get_children(): self.table.delete(row)
        self.status.set("已清空。" if not self.recording else "已清空，正在继续记录。")

    def export(self) -> None:
        target = filedialog.asksaveasfilename(parent=self, defaultextension=".json",
                                              filetypes=[("JSON", "*.json")])
        if target:
            Path(target).write_text(json.dumps(self.events, ensure_ascii=False, indent=2), encoding="utf-8")
            self.status.set(f"已导出 {len(self.events)} 个事件。")


def open_tester(parent: tk.Misc | None = None) -> EventTester:
    return EventTester(parent)
