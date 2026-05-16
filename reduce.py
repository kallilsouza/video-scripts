#!/usr/bin/env python3
"""
Video Size Reducer — PyQt6 GUI
Wraps the ffmpeg hevc_nvenc compression script with a polished interface.
"""

import sys
import os
import subprocess
import re
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSlider,
    QFileDialog,
    QTextEdit,
    QFrame,
    QSizePolicy,
    QProgressBar,
    QCheckBox,
)
from PyQt6.QtCore import (
    Qt,
    QThread,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
)


# ── palette ───────────────────────────────────────────────────────────────────
BG = "#0e0e12"
SURFACE = "#16161d"
CARD = "#1c1c26"
BORDER = "#2a2a38"
ACCENT = "#7c6af7"
ACCENT2 = "#a78bfa"
GREEN = "#34d399"
RED = "#f87171"
AMBER = "#fbbf24"
TEXT = "#e2e2f0"
MUTED = "#6b6b8a"
MONO = "JetBrains Mono, Consolas, monospace"


STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: 'Segoe UI', 'SF Pro Display', system-ui, sans-serif;
}}

/* ── Drop Zone ── */
#dropZone {{
    background: {CARD};
    border: 2px dashed {BORDER};
    border-radius: 16px;
}}
#dropZone:hover {{
    border-color: {ACCENT};
    background: #1e1e2e;
}}

/* ── Cards ── */
#card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

/* ── Buttons ── */
QPushButton#primary {{
    background: {ACCENT};
    color: #fff;
    border: none;
    border-radius: 10px;
    padding: 12px 28px;
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}
QPushButton#primary:hover  {{ background: {ACCENT2}; }}
QPushButton#primary:pressed {{ background: #6254d4; }}
QPushButton#primary:disabled {{
    background: {BORDER};
    color: {MUTED};
}}

QPushButton#browse {{
    background: transparent;
    color: {ACCENT2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#browse:hover {{
    border-color: {ACCENT};
    background: #1e1e2e;
}}

QPushButton#danger {{
    background: transparent;
    color: {RED};
    border: 1px solid #3d1f1f;
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
}}
QPushButton#danger:hover {{ background: #2a1515; border-color: {RED}; }}

/* ── Slider ── */
QSlider::groove:horizontal {{
    background: {BORDER};
    height: 6px;
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT2});
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: #fff;
    border: 2px solid {ACCENT};
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
}}
QSlider::handle:horizontal:hover {{ border-color: {ACCENT2}; }}

/* ── Log ── */
QTextEdit {{
    background: #0a0a0f;
    border: 1px solid {BORDER};
    border-radius: 10px;
    color: #c8c8e0;
    font-family: {MONO};
    font-size: 12px;
    padding: 12px;
    selection-background-color: {ACCENT};
}}

/* ── Progress Bar ── */
QProgressBar {{
    background: {BORDER};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {ACCENT}, stop:1 {GREEN});
    border-radius: 4px;
}}

/* ── CheckBox ── */
QCheckBox {{ color: {MUTED}; font-size: 12px; spacing: 6px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {SURFACE};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEwIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgNEwzLjUgNi41TDkgMSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg==);
}}
QScrollBar:vertical {{
    background: {SURFACE}; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


# ── Worker thread ──────────────────────────────────────────────────────────────
class FFmpegWorker(QThread):
    output = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(int)  # 0-100

    def __init__(self, cmd: list[str], duration_s: float):
        super().__init__()
        self.cmd = cmd
        self.duration_s = duration_s
        self._abort = False

    def run(self):
        try:
            proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            time_re = re.compile(r"time=(\d+):(\d+):([\d.]+)")
            for line in proc.stdout:
                if self._abort:
                    proc.kill()
                    self.finished.emit(False, "Cancelled by user.")
                    return
                self.output.emit(line.rstrip())
                m = time_re.search(line)
                if m and self.duration_s > 0:
                    h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                    elapsed = h * 3600 + mi * 60 + s
                    pct = min(int(elapsed / self.duration_s * 100), 99)
                    self.progress.emit(pct)

            proc.wait()
            if proc.returncode == 0:
                self.progress.emit(100)
                self.finished.emit(True, "Encoding complete ✓")
            else:
                self.finished.emit(False, f"ffmpeg exited with code {proc.returncode}")
        except Exception as e:
            self.finished.emit(False, str(e))

    def abort(self):
        self._abort = True


def get_video_duration(path: str) -> float:
    """Return duration in seconds via ffprobe, or 0 on failure."""
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return float(out.strip())
    except Exception:
        return 0.0


# ── Drop Zone ─────────────────────────────────────────────────────────────────
class DropZone(QFrame):
    fileDropped = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(130)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(6)

        self.icon_lbl = QLabel("⬆")
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl.setStyleSheet(
            f"font-size: 32px; color: {MUTED}; background: transparent;"
        )

        self.title_lbl = QLabel("Drop a video file here")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_lbl.setStyleSheet(
            f"font-size: 15px; font-weight: 600; color: {TEXT}; background: transparent;"
        )

        self.sub_lbl = QLabel("or click Browse to select")
        self.sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_lbl.setStyleSheet(
            f"font-size: 12px; color: {MUTED}; background: transparent;"
        )

        layout.addWidget(self.icon_lbl)
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.sub_lbl)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setStyleSheet(
                f"#dropZone {{ background: #1e1e2e; border: 2px dashed {ACCENT}; border-radius: 16px; }}"
            )

    def dragLeaveEvent(self, _):
        self.setStyleSheet("")

    def dropEvent(self, e: QDropEvent):
        self.setStyleSheet("")
        urls = e.mimeData().urls()
        if urls:
            self.fileDropped.emit(urls[0].toLocalFile())

    def mousePressEvent(self, _):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select video file",
            "",
            "Video files (*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.ts *.flv);;All files (*)",
        )
        if path:
            self.fileDropped.emit(path)

    def set_file(self, name: str):
        self.icon_lbl.setText("🎬")
        self.icon_lbl.setStyleSheet(f"font-size: 28px; background: transparent;")
        self.title_lbl.setText(name)
        self.title_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {ACCENT2}; background: transparent;"
        )
        self.sub_lbl.setText("Click or drop to change file")


# ── Quality Badge ──────────────────────────────────────────────────────────────
def quality_label(pct: int) -> tuple[str, str]:
    """Return (text, color) for a quality-reduction percentage."""
    if pct == 0:
        return "Lossless", GREEN
    if pct <= 20:
        return "Near-lossless", GREEN
    if pct <= 45:
        return "High quality", ACCENT2
    if pct <= 65:
        return "Balanced", AMBER
    if pct <= 85:
        return "Aggressive", "#fb923c"
    return "Maximum compression", RED


# ── Main Window ───────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Reducer")
        self.setMinimumSize(680, 780)
        self.resize(720, 840)
        self.setStyleSheet(STYLESHEET)

        self._input_path = ""
        self._output_path = ""
        self._worker: FFmpegWorker | None = None

        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(28, 28, 28, 28)
        root_layout.setSpacing(18)

        # Header
        header = QLabel("Video Reducer")
        header.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {TEXT}; letter-spacing: -0.5px;"
        )
        sub = QLabel("HEVC / NVENC hardware encoding")
        sub.setStyleSheet(f"font-size: 12px; color: {MUTED};")

        hdr_col = QVBoxLayout()
        hdr_col.setSpacing(2)
        hdr_col.addWidget(header)
        hdr_col.addWidget(sub)

        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.setObjectName("browse")
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.clicked.connect(self._browse)

        hdr_row = QHBoxLayout()
        hdr_row.addLayout(hdr_col)
        hdr_row.addStretch()
        hdr_row.addWidget(self.browse_btn)
        root_layout.addLayout(hdr_row)

        # Drop zone
        self.drop_zone = DropZone()
        self.drop_zone.fileDropped.connect(self._load_file)
        root_layout.addWidget(self.drop_zone)

        # Quality card
        q_card = QFrame()
        q_card.setObjectName("card")
        q_layout = QVBoxLayout(q_card)
        q_layout.setContentsMargins(20, 18, 20, 18)
        q_layout.setSpacing(12)

        q_row = QHBoxLayout()
        q_title = QLabel("Quality reduction")
        q_title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {TEXT};")
        self.q_badge = QLabel("Lossless")
        self.q_badge.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {GREEN}; "
            f"background: #0d2a1e; border-radius: 6px; padding: 2px 10px;"
        )
        q_row.addWidget(q_title)
        q_row.addStretch()
        q_row.addWidget(self.q_badge)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(0)
        self.slider.setTickInterval(10)
        self.slider.valueChanged.connect(self._on_slider)

        marks_row = QHBoxLayout()
        for label, val in [
            ("0%", 0),
            ("25%", None),
            ("50%", None),
            ("75%", None),
            ("100%", 0),
        ]:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"font-size: 10px; color: {MUTED};")
            if val == 0 and label == "0%":
                marks_row.addWidget(lbl)
            elif label == "100%":
                marks_row.addStretch()
                marks_row.addWidget(lbl)
            else:
                marks_row.addStretch()
                marks_row.addWidget(lbl)

        self.pct_lbl = QLabel("0%  →  CQ 0")
        self.pct_lbl.setStyleSheet(
            f"font-size: 11px; color: {MUTED}; font-family: {MONO};"
        )
        self.pct_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        q_layout.addLayout(q_row)
        q_layout.addWidget(self.slider)
        q_layout.addWidget(self.pct_lbl)
        root_layout.addWidget(q_card)

        # Output / options card
        opt_card = QFrame()
        opt_card.setObjectName("card")
        opt_layout = QVBoxLayout(opt_card)
        opt_layout.setContentsMargins(20, 16, 20, 16)
        opt_layout.setSpacing(10)

        out_row = QHBoxLayout()
        out_title = QLabel("Output")
        out_title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {TEXT};")
        self.out_lbl = QLabel("—")
        self.out_lbl.setStyleSheet(
            f"font-size: 12px; color: {MUTED}; font-family: {MONO};"
        )
        self.out_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.out_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        out_row.addWidget(out_title)
        out_row.addWidget(self.out_lbl)
        opt_layout.addLayout(out_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        opt_layout.addWidget(sep)

        self.cuda_cb = QCheckBox(
            "Use CUDA hardware acceleration  (disable if no NVIDIA GPU)"
        )
        self.cuda_cb.setChecked(True)
        opt_layout.addWidget(self.cuda_cb)

        root_layout.addWidget(opt_card)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.hide()
        root_layout.addWidget(self.progress)

        # Action buttons
        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Start Encoding")
        self.run_btn.setObjectName("primary")
        self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self._run)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.hide()
        self.cancel_btn.clicked.connect(self._cancel)

        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch()

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(f"font-size: 12px; color: {MUTED};")
        btn_row.addWidget(self.status_lbl)

        root_layout.addLayout(btn_row)

        # Log
        log_lbl = QLabel("Output log")
        log_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {MUTED}; letter-spacing: 1px;"
        )
        root_layout.addWidget(log_lbl)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(180)
        self.log.setPlaceholderText("ffmpeg output will appear here…")
        root_layout.addWidget(self.log)

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select video file",
            "",
            "Video files (*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.ts *.flv);;All files (*)",
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        self._input_path = path
        p = Path(path)
        self.drop_zone.set_file(p.name)
        out = p.with_name(f"{p.stem}_reduced{p.suffix}")
        self._output_path = str(out)
        self.out_lbl.setText(out.name)
        self.run_btn.setEnabled(True)
        self._log(f"[file] {path}")

    def _on_slider(self, val: int):
        cq = round((val / 100) * 51)
        text, color = quality_label(val)
        bg = color.replace("#", "")
        # tint bg lightly
        self.q_badge.setText(text)
        self.q_badge.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {color}; "
            f"background: {color}22; border-radius: 6px; padding: 2px 10px;"
        )
        self.pct_lbl.setText(f"{val}%  →  CQ {cq}")
        self._update_output_name()

    def _update_output_name(self):
        if not self._input_path:
            return
        p = Path(self._input_path)
        out = p.with_name(f"{p.stem}_reduced{p.suffix}")
        self._output_path = str(out)
        self.out_lbl.setText(out.name)

    def _log(self, text: str):
        self.log.append(text)
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_running(self, running: bool):
        self.run_btn.setVisible(not running)
        self.cancel_btn.setVisible(running)
        self.progress.setVisible(running)
        self.drop_zone.setEnabled(not running)
        self.browse_btn.setEnabled(not running)
        self.slider.setEnabled(not running)
        self.cuda_cb.setEnabled(not running)
        if running:
            self.progress.setValue(0)

    # ── Run ────────────────────────────────────────────────────────────────────
    def _run(self):
        if not self._input_path:
            return
        quality = self.slider.value()
        cq = round((quality / 100) * 51)
        cuda = self.cuda_cb.isChecked()

        cmd = ["ffmpeg", "-y"]
        if cuda:
            cmd += ["-hwaccel", "cuda"]
        cmd += [
            "-i",
            self._input_path,
            "-map_metadata",
            "0",
            "-c:v",
            "hevc_nvenc" if cuda else "libx265",
            "-preset",
            "fast",
            "-cq" if cuda else "-crf",
            str(cq),
            self._output_path,
        ]

        self.log.clear()
        self._log(f"$ {' '.join(cmd)}\n")
        self.status_lbl.setText("Encoding…")

        duration = get_video_duration(self._input_path)
        self._worker = FFmpegWorker(cmd, duration)
        self._worker.output.connect(self._log)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.finished.connect(self._on_done)
        self._worker.start()
        self._set_running(True)

    def _cancel(self):
        if self._worker:
            self._worker.abort()
            self.status_lbl.setText("Cancelling…")
            self.cancel_btn.setEnabled(False)

    def _on_done(self, ok: bool, msg: str):
        self._set_running(False)
        self.cancel_btn.setEnabled(True)
        color = GREEN if ok else RED
        self.status_lbl.setText(msg)
        self.status_lbl.setStyleSheet(f"font-size: 12px; color: {color};")
        self._log(f"\n{'✓' if ok else '✗'} {msg}")
        if ok:
            # show output file size comparison
            try:
                in_sz = os.path.getsize(self._input_path) / 1_048_576
                out_sz = os.path.getsize(self._output_path) / 1_048_576
                saved = 100 - (out_sz / in_sz * 100)
                self._log(
                    f"  Input:  {in_sz:.1f} MB\n"
                    f"  Output: {out_sz:.1f} MB\n"
                    f"  Saved:  {saved:.1f}%"
                )
            except Exception:
                pass


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Video Reducer")

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
