import json
import os
import threading
import time
import tkinter as tk
from dataclasses import asdict, dataclass
from tkinter import messagebox, ttk, filedialog
from typing import List, Optional
from PIL import ImageGrab, Image

try:
    import pyautogui
except ImportError:
    pyautogui = None

# Check for OpenCV (required for confidence-based image matching)
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


@dataclass
class ActionItem:
    kind: str  # "mouse", "key", "text", "image_click", "image_wait"
    delay: int = 100
    x: int = 0
    y: int = 0
    key: str = "ctrl"
    key_action: str = "press"
    text: str = ""
    image_path: str = ""
    timeout: int = 10          # for image_wait
    confidence: float = 0.8    # for image matching


class AutoClickerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Enhanced Auto Clicker (Image Recognition)")
        self.root.geometry("1080x720")
        self.root.minsize(980, 560)

        self.actions: List[ActionItem] = []
        self.save_path = os.path.join(os.path.dirname(__file__), "actions.json")
        self.image_dir = os.path.join(os.path.dirname(__file__), "templates")
        if not os.path.exists(self.image_dir):
            os.makedirs(self.image_dir)

        self.is_running = False
        self.stop_requested = False

        self._build_ui()
        self._check_dependencies()

    def _check_dependencies(self):
        if not OPENCV_AVAILABLE:
            messagebox.showwarning(
                "Missing OpenCV",
                "Image recognition (confidence) requires OpenCV.\n"
                "Install it with: pip install opencv-python\n"
                "Image actions will be disabled until you install it."
            )

    def _build_ui(self) -> None:
        # Top toolbar
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Repetitions:").pack(side="left")
        self.repetitions_var = tk.IntVar(value=1)
        ttk.Spinbox(top, from_=1, to=10_000_000, textvariable=self.repetitions_var, width=12).pack(side="left", padx=(6, 12))

        ttk.Button(top, text="Add Mouse Click", command=self._add_mouse_row).pack(side="left", padx=2)
        ttk.Button(top, text="Add Key Press", command=self._add_key_row).pack(side="left", padx=2)
        ttk.Button(top, text="Add Text", command=self._add_text_row).pack(side="left", padx=2)
        ttk.Button(top, text="Add Image Click", command=self._add_image_click_row).pack(side="left", padx=2)
        ttk.Button(top, text="Add Image Wait", command=self._add_image_wait_row).pack(side="left", padx=2)
        ttk.Button(top, text="Start", command=self._start_actions).pack(side="left", padx=10)
        ttk.Button(top, text="Stop", command=self._stop_actions).pack(side="left", padx=2)
        ttk.Button(top, text="Save", command=self._save_actions).pack(side="left", padx=2)
        ttk.Button(top, text="Load", command=self._load_actions).pack(side="left", padx=2)
        ttk.Button(top, text="Capture Image", command=self._start_region_capture).pack(side="left", padx=2)

        # Canvas for scrollable action list
        self.canvas = tk.Canvas(self.root, borderwidth=0, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.scrollable = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable, anchor="nw")

        self.scrollable.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

        # Log area
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=5)
        log_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.log_text = tk.Text(log_frame, height=8, font=("Consolas", 9), state="disabled", bg="#f0f0f0")
        self.log_text.pack(fill="both", expand=True)

    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    # ----- Action Adders -----
    def _add_mouse_row(self):
        self.actions.append(ActionItem(kind="mouse"))
        self._render_rows()

    def _add_key_row(self):
        self.actions.append(ActionItem(kind="key"))
        self._render_rows()

    def _add_text_row(self):
        self.actions.append(ActionItem(kind="text"))
        self._render_rows()

    def _add_image_click_row(self):
        if not OPENCV_AVAILABLE:
            messagebox.showerror("OpenCV missing", "Image actions require OpenCV.\nInstall: pip install opencv-python")
            return
        self.actions.append(ActionItem(kind="image_click"))
        self._render_rows()

    def _add_image_wait_row(self):
        if not OPENCV_AVAILABLE:
            messagebox.showerror("OpenCV missing", "Image actions require OpenCV.\nInstall: pip install opencv-python")
            return
        self.actions.append(ActionItem(kind="image_wait"))
        self._render_rows()

    # ----- Rendering -----
    def _render_rows(self):
        # Clear existing widgets
        for widget in self.scrollable.winfo_children():
            widget.destroy()

        for idx, action in enumerate(self.actions):
            row = ttk.LabelFrame(self.scrollable, text=f"Action {idx + 1} ({action.kind})", padding=8)
            row.pack(fill="x", padx=4, pady=4)

            # Render based on kind
            if action.kind == "mouse":
                self._render_mouse_row(row, action, idx)
            elif action.kind == "key":
                self._render_key_row(row, action, idx)
            elif action.kind == "text":
                self._render_text_row(row, action, idx)
            elif action.kind in ("image_click", "image_wait"):
                self._render_image_row(row, action, idx)

            # Common delay and delete
            ttk.Label(row, text="Delay (ms)").grid(row=0, column=10, padx=(12, 4))
            delay_var = tk.IntVar(value=action.delay)
            delay_spin = ttk.Spinbox(row, from_=0, to=60000, textvariable=delay_var, width=8)
            delay_spin.grid(row=0, column=11, padx=(0, 8))
            delay_spin.bind("<<FocusOut>>", lambda e, a=action, var=delay_var: setattr(a, "delay", int(var.get())))
            delay_spin.bind("<Return>", lambda e, a=action, var=delay_var: setattr(a, "delay", int(var.get())))

            ttk.Button(row, text="Delete", command=lambda i=idx: self._delete_action(i)).grid(row=0, column=12)

            row.columnconfigure(1, weight=1)

    def _render_mouse_row(self, row, action, idx):
        ttk.Label(row, text="Mouse click").grid(row=0, column=0, sticky="w")
        ttk.Label(row, text="x:").grid(row=0, column=1, padx=(10, 2))
        x_var = tk.StringVar(value=str(action.x))
        x_entry = ttk.Entry(row, textvariable=x_var, width=8)
        x_entry.grid(row=0, column=2, padx=(0, 6))
        x_entry.bind("<FocusOut>", lambda e, a=action, var=x_var: self._update_mouse_coord(a, var, "x"))
        x_entry.bind("<Return>", lambda e, a=action, var=x_var: self._update_mouse_coord(a, var, "x"))

        ttk.Label(row, text="y:").grid(row=0, column=3, padx=(4, 2))
        y_var = tk.StringVar(value=str(action.y))
        y_entry = ttk.Entry(row, textvariable=y_var, width=8)
        y_entry.grid(row=0, column=4, padx=(0, 6))
        y_entry.bind("<FocusOut>", lambda e, a=action, var=y_var: self._update_mouse_coord(a, var, "y"))
        y_entry.bind("<Return>", lambda e, a=action, var=y_var: self._update_mouse_coord(a, var, "y"))

        ttk.Button(row, text="Select Point", command=lambda a=action: self._select_point(a)).grid(row=0, column=5, padx=4)

    def _render_key_row(self, row, action, idx):
        ttk.Label(row, text="Key").grid(row=0, column=0, sticky="w")
        key_var = tk.StringVar(value=action.key)
        key_box = ttk.Combobox(row, textvariable=key_var, state="readonly", width=12, values=self._key_options())
        key_box.grid(row=0, column=1, padx=(10, 6))
        key_box.bind("<<ComboboxSelected>>", lambda e, a=action, var=key_var: setattr(a, "key", var.get()))

        ttk.Label(row, text="Type").grid(row=0, column=2, padx=(8, 4))
        key_type_var = tk.StringVar(value=action.key_action)
        key_type_box = ttk.Combobox(row, textvariable=key_type_var, state="readonly", width=10, values=["press", "down", "up"])
        key_type_box.grid(row=0, column=3, padx=(0, 6))
        key_type_box.bind("<<ComboboxSelected>>", lambda e, a=action, var=key_type_var: setattr(a, "key_action", var.get()))

    def _render_text_row(self, row, action, idx):
        ttk.Label(row, text="Text").grid(row=0, column=0, sticky="w")
        text_var = tk.StringVar(value=action.text)
        entry = ttk.Entry(row, textvariable=text_var, width=28)
        entry.grid(row=0, column=1, padx=(10, 6), sticky="ew")
        entry.bind("<KeyRelease>", lambda e, a=action, var=text_var: setattr(a, "text", var.get()))

    def _render_image_row(self, row, action, idx):
        ttk.Label(row, text="Image path:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        path_var = tk.StringVar(value=action.image_path)
        path_entry = ttk.Entry(row, textvariable=path_var, width=30)
        path_entry.grid(row=0, column=1, padx=(0, 6), sticky="ew")
        path_entry.bind("<KeyRelease>", lambda e, a=action, var=path_var: setattr(a, "image_path", var.get()))

        ttk.Button(row, text="Browse", command=lambda a=action: self._browse_image(a)).grid(row=0, column=2, padx=4)

        if action.kind == "image_wait":
            ttk.Label(row, text="Timeout (s):").grid(row=0, column=3, padx=(8, 4))
            timeout_var = tk.IntVar(value=action.timeout)
            timeout_spin = ttk.Spinbox(row, from_=1, to=60, textvariable=timeout_var, width=6)
            timeout_spin.grid(row=0, column=4, padx=(0, 6))
            timeout_spin.bind("<<FocusOut>>", lambda e, a=action, var=timeout_var: setattr(a, "timeout", int(var.get())))

        # Confidence slider
        ttk.Label(row, text="Confidence:").grid(row=0, column=5, padx=(8, 4))
        conf_var = tk.DoubleVar(value=action.confidence)
        conf_scale = ttk.Scale(row, from_=0.5, to=1.0, orient=tk.HORIZONTAL, variable=conf_var, length=100)
        conf_scale.grid(row=0, column=6, padx=(0, 6))
        conf_scale.bind("<ButtonRelease-1>", lambda e, a=action, var=conf_var: setattr(a, "confidence", var.get()))

    def _update_mouse_coord(self, action, value_var, axis):
        try:
            numeric = int(value_var.get())
        except ValueError:
            return
        if axis == "x":
            action.x = numeric
        else:
            action.y = numeric

    def _select_point(self, action):
        """Fullscreen overlay to pick a point."""
        self.pending_target = action
        if hasattr(self, 'overlay_window') and self.overlay_window:
            self.overlay_window.destroy()

        self.overlay_window = tk.Toplevel(self.root)
        self.overlay_window.attributes("-fullscreen", True)
        self.overlay_window.attributes("-topmost", True)
        self.overlay_window.attributes("-alpha", 0.20)
        self.overlay_window.overrideredirect(True)
        self.overlay_window.configure(bg="black")
        self.overlay_window.bind("<Escape>", self._cancel_selection)
        self.overlay_window.bind("<Button-1>", self._capture_selected_point)
        self.overlay_window.bind("<Motion>", self._move_crosshair)
        self.overlay_window.bind("<Leave>", self._move_crosshair)

        self.overlay_canvas = tk.Canvas(self.overlay_window, bg="black", highlightthickness=0)
        self.overlay_canvas.pack(fill="both", expand=True)
        self.overlay_canvas.create_text(20, 20, text="Click anywhere to pick a point. Press Esc to cancel.",
                                        anchor="nw", fill="white", font=("Segoe UI", 12))
        self.overlay_canvas.focus_set()
        self._move_crosshair(None)

    def _move_crosshair(self, event):
        if not hasattr(self, 'overlay_window') or not self.overlay_window:
            return
        if event is None:
            x = self.overlay_window.winfo_pointerx()
            y = self.overlay_window.winfo_pointery()
        else:
            x = event.x_root
            y = event.y_root
        self.overlay_canvas.delete("crosshair")
        self.overlay_canvas.create_line(x - 20, y, x + 20, y, fill="red", width=2, tag="crosshair")
        self.overlay_canvas.create_line(x, y - 20, x, y + 20, fill="red", width=2, tag="crosshair")
        self.overlay_canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill="red", outline="red", tag="crosshair")

    def _capture_selected_point(self, event):
        if self.pending_target is None:
            return
        self.pending_target.x = event.x_root
        self.pending_target.y = event.y_root
        self._close_selection_overlay()
        self._render_rows()
        messagebox.showinfo("Point selected", f"Saved coordinates: {self.pending_target.x}, {self.pending_target.y}")

    def _cancel_selection(self, event):
        self._close_selection_overlay()

    def _close_selection_overlay(self):
        if hasattr(self, 'overlay_window') and self.overlay_window:
            self.overlay_window.destroy()
            self.overlay_window = None
        self.pending_target = None

    def _browse_image(self, action):
        path = filedialog.askopenfilename(
            title="Select template image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif")]
        )
        if path:
            action.image_path = path
            self._render_rows()

    def _delete_action(self, index):
        if 0 <= index < len(self.actions):
            del self.actions[index]
            self._render_rows()

    def _start_actions(self):
        if pyautogui is None:
            messagebox.showerror("Dependency missing", "pyautogui not installed.")
            return

        if self.is_running:
            messagebox.showinfo("Already running", "Macro is already running.")
            return

        self.is_running = True
        self.stop_requested = False
        repetitions = max(1, self.repetitions_var.get())
        threading.Thread(target=self._run_actions, args=(repetitions,), daemon=True).start()
        self._log("▶️ Macro started.")

    def _stop_actions(self):
        if self.is_running:
            self.stop_requested = True
            self._log("⏹️ Stop requested...")

    def _run_actions(self, repetitions):
        for rep in range(repetitions):
            if self.stop_requested or not self.is_running:
                break
            self._log(f"--- Repetition {rep+1}/{repetitions} ---")
            for action in self.actions:
                if self.stop_requested:
                    break
                try:
                    if action.kind == "mouse":
                        self._perform_mouse(action)
                    elif action.kind == "key":
                        self._perform_key(action)
                    elif action.kind == "text":
                        self._perform_text(action)
                    elif action.kind == "image_click":
                        self._perform_image_click(action)
                    elif action.kind == "image_wait":
                        self._perform_image_wait(action)
                except Exception as e:
                    self._log(f"❌ Error in action {action.kind}: {e}")
                    break
                if action.delay > 0:
                    time.sleep(action.delay / 1000.0)
        self.is_running = False
        self._log("✅ Macro finished.")

    # ----- Action Performers -----
    def _perform_mouse(self, action):
        pyautogui.moveTo(action.x, action.y, duration=0.05)
        pyautogui.click()

    def _perform_key(self, action):
        key = action.key.lower()
        if action.key_action == "down":
            pyautogui.keyDown(key)
        elif action.key_action == "up":
            pyautogui.keyUp(key)
        else:
            pyautogui.press(key)

    def _perform_text(self, action):
        if action.text:
            pyautogui.write(action.text)

    def _perform_image_click(self, action):
        if not os.path.exists(action.image_path):
            self._log(f"[!] Image file not found: {action.image_path}")
            return
        try:
            location = pyautogui.locateOnScreen(
                action.image_path,
                confidence=action.confidence,
                grayscale=False
            )
            if location:
                center = pyautogui.center(location)
                self._log(f"[*] Found image at {center}")
                pyautogui.moveTo(center.x, center.y, duration=0.1)
                pyautogui.click()
            else:
                self._log(f"[!] Image not found: {action.image_path}")
        except Exception as e:
            self._log(f"[!] Image click error: {type(e).__name__}: {e}")

    def _perform_image_wait(self, action):
        if not os.path.exists(action.image_path):
            self._log(f"[!] Image file not found: {action.image_path}")
            return
        timeout = max(1, action.timeout)
        start = time.time()
        found = False
        while time.time() - start < timeout and not self.stop_requested:
            try:
                location = pyautogui.locateOnScreen(
                    action.image_path,
                    confidence=action.confidence,
                    grayscale=False
                )
                if location:
                    found = True
                    break
            except Exception:
                pass
            time.sleep(0.2)
        if found:
            self._log(f"[✓] Image appeared: {action.image_path}")
        else:
            self._log(f"[!] Image wait timeout: {action.image_path}")

    # ----- Save/Load -----
    def _save_actions(self):
        try:
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump([asdict(action) for action in self.actions], f, indent=2)
            messagebox.showinfo("Saved", f"Actions saved to {self.save_path}")
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    def _load_actions(self):
        if not os.path.exists(self.save_path):
            messagebox.showinfo("No file", "No saved actions file found.")
            return
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.actions = [ActionItem(**item) for item in data]
            self._render_rows()
            messagebox.showinfo("Loaded", f"Loaded {len(self.actions)} actions.")
        except Exception as e:
            messagebox.showerror("Load error", str(e))

    # ----- Region Capture for Templates -----
    def _start_region_capture(self):
        """Opens a fullscreen overlay to drag‑select a region, then saves it as a PNG."""
        if pyautogui is None:
            messagebox.showerror("Dependency missing", "pyautogui not installed.")
            return

        # Hide main window to let user see the screen
        self.root.withdraw()
        time.sleep(0.3)

        # Create a transparent fullscreen window
        capture_win = tk.Toplevel(self.root)
        capture_win.attributes("-fullscreen", True)
        capture_win.attributes("-topmost", True)
        capture_win.attributes("-alpha", 0.3)
        capture_win.overrideredirect(True)
        capture_win.configure(bg="black")
        capture_win.bind("<Escape>", lambda e: self._cancel_capture(capture_win))
        capture_win.bind("<ButtonPress-1>", self._on_capture_press)
        capture_win.bind("<B1-Motion>", self._on_capture_drag)
        capture_win.bind("<ButtonRelease-1>", self._on_capture_release)

        # Canvas for drawing rectangle
        self.capture_canvas = tk.Canvas(capture_win, bg="black", highlightthickness=0)
        self.capture_canvas.pack(fill="both", expand=True)

        # Variables for selection
        self.capture_start = None
        self.capture_rect = None
        self.capture_win = capture_win

        # Instructions
        self.capture_canvas.create_text(20, 20, anchor="nw",
                                        text="Drag to select region. Press Esc to cancel.",
                                        fill="white", font=("Segoe UI", 12))

    def _on_capture_press(self, event):
        self.capture_start = (event.x_root, event.y_root)
        if self.capture_rect:
            self.capture_canvas.delete(self.capture_rect)

    def _on_capture_drag(self, event):
        if self.capture_start is None:
            return
        x1, y1 = self.capture_start
        x2, y2 = event.x_root, event.y_root
        if self.capture_rect:
            self.capture_canvas.delete(self.capture_rect)
        self.capture_rect = self.capture_canvas.create_rectangle(
            x1, y1, x2, y2,
            outline="red", width=2
        )

    def _on_capture_release(self, event):
        if self.capture_start is None:
            return
        x1, y1 = self.capture_start
        x2, y2 = event.x_root, event.y_root
        # Ensure correct order
        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1, x2)
        bottom = max(y1, y2)
        width = right - left
        height = bottom - top

        if width < 10 or height < 10:
            messagebox.showwarning("Too small", "Selection too small. Try again.")
            self._cancel_capture(self.capture_win)
            return

        # Capture the screen region using PIL
        try:
            img = ImageGrab.grab(bbox=(left, top, right, bottom))
            # Ask for filename
            from tkinter import simpledialog
            default_name = f"template_{int(time.time())}.png"
            name = simpledialog.askstring("Save Template", "Enter filename (without extension):",
                                          initialvalue="template")
            if name is None:
                self._cancel_capture(self.capture_win)
                return
            if not name.endswith(".png"):
                name += ".png"
            full_path = os.path.join(self.image_dir, name)
            img.save(full_path)
            messagebox.showinfo("Template saved", f"Saved to {full_path}")
            self._log(f"[✓] Template saved: {full_path}")
        except Exception as e:
            messagebox.showerror("Capture error", str(e))
        finally:
            self._cancel_capture(self.capture_win)

    def _cancel_capture(self, capture_win=None):
        if capture_win is None and hasattr(self, 'capture_win'):
            capture_win = self.capture_win
        if capture_win:
            capture_win.destroy()
        self.root.deiconify()
        self.root.focus_force()

    # ----- Utility -----
    @staticmethod
    def _key_options():
        return [
            "ctrl", "shift", "alt", "enter", "escape", "tab", "backspace",
            "space", "left", "right", "up", "down", "f1", "f2", "f3", "f4",
            "f5", "f6", "f7", "f8", "f9", "f10", "a", "b", "c", "d", "e",
            "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r",
            "s", "t", "u", "v", "w", "x", "y", "z"
        ]


def main():
    root = tk.Tk()
    app = AutoClickerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()