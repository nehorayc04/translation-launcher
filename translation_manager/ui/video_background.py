"""
Looped video background — decodes on a worker thread, hands the latest
frame to the UI via a one-slot queue, and polls that queue from the
Tk event loop.

Why a queue (not `after()` from the worker):
  Cross-thread `widget.after(...)` calls are not reliably handled by
  CPython's tkinter — the scheduled callback can be silently dropped
  on Windows. Polling a `queue.Queue` from the UI thread is the
  thread-safe pattern.
"""

import queue
import threading
import time
import tkinter as tk
from pathlib import Path

try:
    import cv2
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False


class VideoBackground(tk.Label):
    """A `tk.Label` that displays a looped video as its image."""

    def __init__(
        self,
        master,
        video_path: str | Path,
        fps_cap: int = 30,
        bg: str = "#070710",
        blur_radius: int = 41,    # odd kernel for cv2.GaussianBlur; 0 = no blur
        darken: float = 0.55,     # multiplied into pixel values; 1.0 = no dim
        **kwargs,
    ):
        super().__init__(
            master, bd=0, highlightthickness=0, bg=bg, **kwargs,
        )
        self.video_path = str(video_path)
        self.fps_cap = fps_cap
        # Frosted-glass treatment — heavy blur + darken so the UI on top
        # stays readable and the video reads as "ambient depth"
        self.blur_radius = blur_radius
        self.darken = darken

        self._running = False
        self._cap = None
        self._photo = None        # PhotoImage reference (prevents GC)
        self._target_size = (0, 0)
        self._frame_queue: "queue.Queue" = queue.Queue(maxsize=1)
        self._poll_interval_ms = max(16, int(1000 / fps_cap))

        self.bind("<Configure>", self._on_resize)

        if not _HAS_CV2:
            self.configure(text="(install opencv-python to enable video bg)",
                           fg="#ffaa00")
            return
        if not Path(self.video_path).exists():
            self.configure(text=f"(video missing: {self.video_path})",
                           fg="#ff6644")
            return

        self._running = True
        self._thread = threading.Thread(target=self._decode_loop, daemon=True)
        self._thread.start()
        # Start polling on the UI thread
        self.after(50, self._poll)

    # ─────────────────────────────────────────────────────────
    def _on_resize(self, e) -> None:
        if e.width > 1 and e.height > 1:
            self._target_size = (e.width, e.height)

    # ─────────────────────────────────────────────────────────
    def _decode_loop(self) -> None:
        """Background thread — reads, resizes, color-converts. Hands the
        frame to the UI via the one-slot queue (replacing any stale frame)."""
        import traceback
        try:
            self._cap = cv2.VideoCapture(self.video_path)
            if not self._cap.isOpened():
                print(f"[VideoBackground] FAILED to open {self.video_path}",
                      flush=True)
                return
            src_fps = self._cap.get(cv2.CAP_PROP_FPS) or 30
            fps = min(self.fps_cap, max(15, int(src_fps)))
            interval = 1.0 / fps

            while self._running:
                start = time.time()
                ret, frame = self._cap.read()
                if not ret:
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue

                tw, th = self._target_size
                if tw > 1 and th > 1:
                    frame = cv2.resize(frame, (tw, th),
                                       interpolation=cv2.INTER_LINEAR)
                # Frosted-glass effect: heavy Gaussian blur + brightness scale.
                # Done on the decode thread so the UI stays smooth.
                if self.blur_radius and self.blur_radius >= 3:
                    k = self.blur_radius | 1   # ensure odd
                    frame = cv2.GaussianBlur(frame, (k, k), 0)
                if 0.0 <= self.darken < 1.0:
                    frame = (frame * self.darken).astype(frame.dtype)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Replace any stale frame still in the queue. We never want
                # the UI painting frames the worker decoded seconds ago.
                try:
                    self._frame_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._frame_queue.put_nowait(frame_rgb)
                except queue.Full:
                    pass

                elapsed = time.time() - start
                if elapsed < interval:
                    time.sleep(interval - elapsed)
        except Exception as e:
            print(f"[VideoBackground] decode error: {type(e).__name__}: {e}",
                  flush=True)
            traceback.print_exc()
        finally:
            try:
                if self._cap is not None:
                    self._cap.release()
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────
    def _poll(self) -> None:
        """Runs on the UI thread — drains the queue and paints the
        latest frame, then re-schedules itself."""
        frame_rgb = None
        try:
            frame_rgb = self._frame_queue.get_nowait()
        except queue.Empty:
            pass

        if frame_rgb is not None:
            try:
                from PIL import Image, ImageTk
                pil = Image.fromarray(frame_rgb)
                self._photo = ImageTk.PhotoImage(pil)
                self.configure(image=self._photo)
            except Exception:
                pass

        try:
            if self.winfo_exists() and self._running:
                self.after(self._poll_interval_ms, self._poll)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────
    def stop(self) -> None:
        self._running = False
