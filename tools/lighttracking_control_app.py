#!/usr/bin/env python3
"""Simple desktop app to control the LightTracking systemd service."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ModuleNotFoundError:
    tk = None
    ttk = None
    messagebox = None


class LightTrackingControlApp:
    def __init__(self, root: tk.Tk, service_name: str) -> None:
        self.root = root
        self.service_name = service_name
        self.root.title("LightTracking Service Control")
        self.root.minsize(520, 280)
        self.root.resizable(False, False)

        self.status_var = tk.StringVar(value="Status: unbekannt")
        self.enabled_var = tk.StringVar(value="Autostart: unbekannt")
        self.last_update_var = tk.StringVar(value="Letztes Update: -")
        self.detail_var = tk.StringVar(value="")
        self.busy = False

        self.status_style = ttk.Style(self.root)
        self.status_style.configure("Status.TLabel", foreground="#a06100")

        self._build_ui()
        self.refresh_status()
        self.root.after(3000, self._auto_refresh)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=14)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text=f"Service: {self.service_name}",
            font=("Sans", 12, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        self.lbl_status = ttk.Label(frame, textvariable=self.status_var, font=("Sans", 11), style="Status.TLabel")
        self.lbl_status.pack(anchor=tk.W)
        ttk.Label(frame, textvariable=self.enabled_var).pack(anchor=tk.W, pady=(4, 0))
        ttk.Label(frame, textvariable=self.last_update_var).pack(anchor=tk.W, pady=(4, 0))
        ttk.Label(frame, textvariable=self.detail_var, foreground="#444").pack(anchor=tk.W, pady=(6, 12))

        buttons = ttk.Frame(frame)
        buttons.pack(anchor=tk.W, pady=(0, 10))

        self.btn_start = ttk.Button(buttons, text="Start", width=14, command=lambda: self.run_action("start"))
        self.btn_stop = ttk.Button(buttons, text="Stop", width=14, command=lambda: self.run_action("stop"))
        self.btn_restart = ttk.Button(buttons, text="Restart", width=14, command=lambda: self.run_action("restart"))
        self.btn_refresh = ttk.Button(buttons, text="Status aktualisieren", width=18, command=self.refresh_status)

        self.btn_start.grid(row=0, column=0, padx=(0, 8), pady=4)
        self.btn_stop.grid(row=0, column=1, padx=(0, 8), pady=4)
        self.btn_restart.grid(row=0, column=2, padx=(0, 8), pady=4)
        self.btn_refresh.grid(row=0, column=3, pady=4)

        hints = (
            "Hinweis: Fuer Start/Stop/Restart wird ein Admin-Passwort abgefragt "
            "(pkexec / Polkit)."
        )
        ttk.Label(frame, text=hints, wraplength=480, foreground="#666").pack(anchor=tk.W)

    def _run_cmd(self, cmd: list[str]) -> tuple[int, str]:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, output.strip()

    def _run_systemctl(self, action: str, use_pkexec: bool = False) -> tuple[int, str]:
        cmd = ["systemctl", action, self.service_name]
        if use_pkexec:
            if shutil.which("pkexec") is None:
                return 127, "pkexec nicht gefunden. Bitte package policykit-1 installieren."
            cmd = ["pkexec"] + cmd
        return self._run_cmd(cmd)

    def _set_busy(self, state: bool) -> None:
        self.busy = state
        disabled = tk.DISABLED if state else tk.NORMAL
        for btn in (self.btn_start, self.btn_stop, self.btn_restart, self.btn_refresh):
            btn.configure(state=disabled)

    def _auto_refresh(self) -> None:
        if self.root.winfo_exists():
            self.refresh_status()
            self.root.after(3000, self._auto_refresh)

    def refresh_status(self, force: bool = False) -> None:
        if self.busy and not force:
            return

        rc_active, active = self._run_cmd(["systemctl", "is-active", self.service_name])
        rc_enabled, enabled = self._run_cmd(["systemctl", "is-enabled", self.service_name])
        rc_sub, sub_state = self._run_cmd(["systemctl", "show", self.service_name, "-p", "SubState", "--value"])

        active_text = active if active else "unbekannt"
        enabled_text = enabled if enabled else "unbekannt"
        sub_text = sub_state if rc_sub == 0 and sub_state else "-"

        if rc_active == 0 and active_text == "active":
            color = "#0a7f2e"
        elif active_text in {"failed", "inactive"}:
            color = "#b02121"
        else:
            color = "#a06100"

        self.status_var.set(f"Status: {active_text}")
        self.enabled_var.set(f"Autostart: {enabled_text}")
        self.last_update_var.set(f"Letztes Update: {datetime.now().strftime('%H:%M:%S')}")
        self.detail_var.set(f"SubState: {sub_text}")
        self.status_style.configure("Status.TLabel", foreground=color)

    def run_action(self, action: str) -> None:
        self._set_busy(True)
        try:
            rc, output = self._run_systemctl(action, use_pkexec=True)
            if rc != 0:
                msg = output or f"{action} fehlgeschlagen (Exit-Code {rc})."
                messagebox.showerror("LightTracking", msg)
        finally:
            self._set_busy(False)
        self.refresh_status(force=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LightTracking Service Control")
    parser.add_argument("--service", default="lighttracking", help="Systemd service name (default: lighttracking)")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if tk is None or ttk is None or messagebox is None:
        print(
            "tkinter ist nicht installiert. Bitte installiere zuerst: sudo apt install -y python3-tk",
            file=sys.stderr,
        )
        return 2
    root = tk.Tk()
    app = LightTrackingControlApp(root, args.service)
    app.refresh_status()
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
