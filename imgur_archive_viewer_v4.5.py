import ctypes
import platform
import os
import re
import sys
import shutil
import queue
import time
import threading
import webbrowser
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

import requests
import sv_ttk
from PIL import Image, ImageTk

# --- Optional imports ---
try:
    import darkdetect
except ImportError:
    darkdetect = None

if os.name == "nt":
    try:
        import pywinstyles
    except ImportError:
        pywinstyles = None
    # Enable High DPI support
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
else:
    pywinstyles = None

# --- Constants ---
EXTENSIONS = [".jpg", ".png", ".gif", ".gifv", ".mp4", ".webm", ".mpeg"]
PRIORITY_EXTENSIONS = [".mp4", ".webm", ".gif", ".png", ".jpg", ".mpeg", ".gifv"]
MIME_TYPE_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/mpeg": ".mpeg",
}


# --- Utilities ---
def get_config_dir(app_name="ImgurArchiveHunter"):
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    path = os.path.join(base, app_name)
    os.makedirs(path, exist_ok=True)
    return path


def load_settings(filename="settings.json"):
    path = os.path.join(get_config_dir(), filename)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_settings(data, filename="settings.json"):
    path = os.path.join(get_config_dir(), filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def human_size(num_bytes):
    try:
        size = float(num_bytes)
    except Exception:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    for u in units:
        if size < 1024.0:
            return f"{size:.1f} {u}"
        size /= 1024.0
    return f"{size:.1f} PB"


class Tooltip:
    """Modern tooltip with fade effect simulation."""

    def __init__(self, widget, text, delay=600):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._id = None
        self._tip = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)

    def _schedule(self, _):
        self._id = self.widget.after(self.delay, self._show)

    def _show(self):
        if self._tip: return
        x, y, _, _ = self.widget.bbox("insert") or (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 10
        y += self.widget.winfo_rooty() + 30
        self._tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(tw, text=self.text, padding=(8, 4), style="Tooltip.TLabel")
        label.pack()

    def _hide(self, _):
        if self._id:
            self.widget.after_cancel(self._id)
            self._id = None
        if self._tip:
            self._tip.destroy()
            self._tip = None


# --- Main Application ---
class ImgurArchiveAppV4_5:
    def __init__(self, root):
        self.root = root
        self.root.title("Imgur Archive Hunter")
        self.root.geometry("1000x800")
        self.root.minsize(800, 600)

        # State
        self.settings = load_settings()
        self.app_state = "IDLE"
        self.most_recent_download = None
        self.active_thread = None
        self.cancel_event = threading.Event()
        self.progress_queue = queue.Queue()
        self.batch_items = {}
        self.first_success_previewed = False
        self._batch_start_time = None
        self._last_width = 0
        self._last_height = 0

        # Theme Init
        self._init_theme()

        # Core Components
        self.http_session = requests.Session()

        # UI Construction
        self._create_styles()
        self._create_layout()

        # Restore State
        self._restore_initial_state()
        self._set_ui_state("IDLE")

        # Loops & Binds
        self.root.after(100, self._process_progress_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._apply_shortcuts()
        self._configure_tooltips()
        self.root.bind("<Configure>", self._on_window_configure)

    def _init_theme(self):
        if darkdetect and darkdetect.theme():
            initial_theme = darkdetect.theme().lower()
            sv_ttk.set_theme(initial_theme)
            self.is_dark_mode = initial_theme == "dark"
        else:
            theme = self.settings.get("theme", "dark")
            sv_ttk.set_theme(theme)
            self.is_dark_mode = theme == "dark"

        if pywinstyles and os.name == "nt":
            try:
                # Apply Mica effect if available (Windows 11)
                pywinstyles.apply_style(self.root, "dark" if self.is_dark_mode else "light")
                pywinstyles.change_header_color(self.root, "#1c1c1c" if self.is_dark_mode else "#fafafa")
            except:
                pass

    def _create_styles(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("SubHeader.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 11, "bold"))
        style.configure("Mono.TLabel", font=("Consolas", 9))
        style.configure("Tooltip.TLabel", background="#333" if self.is_dark_mode else "#eee", relief="solid",
                        borderwidth=0)

        # Treeview specific
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _create_layout(self):
        # Main Grid Config
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)  # Header
        self.root.rowconfigure(1, weight=0)  # Controls
        self.root.rowconfigure(2, weight=1)  # Main Content
        self.root.rowconfigure(3, weight=0)  # Status

        # 1. Header Bar
        header_frame = ttk.Frame(self.root, padding=(20, 15))
        header_frame.grid(row=0, column=0, sticky="ew")

        ttk.Label(header_frame, text="Imgur Archive Hunter", style="Title.TLabel").pack(side="left")

        ctrl_frame = ttk.Frame(header_frame)
        ctrl_frame.pack(side="right")
        self.theme_btn = ttk.Button(ctrl_frame, text="🌗", command=self.toggle_theme, width=4)
        self.theme_btn.pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="About", command=self._show_about).pack(side="left")

        # 2. Control Panel (Card Style)
        control_card = ttk.LabelFrame(self.root, text="Configuration & Job Setup", padding=15)
        control_card.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        control_card.columnconfigure(1, weight=1)

        # -- Row 1: Save Location --
        ttk.Label(control_card, text="Save To:", style="SubHeader.TLabel").grid(row=0, column=0, sticky="w", pady=5)
        self.save_location_var = tk.StringVar(value=self.settings.get("save_folder", os.getcwd()))

        loc_frame = ttk.Frame(control_card)
        loc_frame.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(10, 0))
        loc_frame.columnconfigure(0, weight=1)

        ttk.Entry(loc_frame, textvariable=self.save_location_var).grid(row=0, column=0, sticky="ew")
        self.browse_save_btn = ttk.Button(loc_frame, text="📂", width=4, command=self._browse_save_location)
        self.browse_save_btn.grid(row=0, column=1, padx=(5, 0))

        # -- Row 2: Input Method (Notebook) & Options --

        # Left Side: Input Tabs
        self.input_tabs = ttk.Notebook(control_card)
        self.input_tabs.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(15, 0))

        # Tab 1: Single
        self.tab_single = ttk.Frame(self.input_tabs, padding=15)
        self.input_tabs.add(self.tab_single, text="  Single URL  ")
        self.url_entry = ttk.Entry(self.tab_single)
        self.url_entry.pack(fill="x", expand=True)
        ttk.Label(self.tab_single, text="Paste an Imgur ID or full URL (e.g. imgur.com/a/abcde)",
                  font=("Segoe UI", 8)).pack(anchor="w", pady=(5, 0))

        # Tab 2: Batch
        self.tab_batch = ttk.Frame(self.input_tabs, padding=15)
        self.input_tabs.add(self.tab_batch, text="  Batch File (.txt)  ")
        batch_inner = ttk.Frame(self.tab_batch)
        batch_inner.pack(fill="x", expand=True)
        self.batch_file_var = tk.StringVar()
        ttk.Entry(batch_inner, textvariable=self.batch_file_var, state="readonly").pack(side="left", fill="x",
                                                                                        expand=True)
        self.browse_batch_btn = ttk.Button(batch_inner, text="📂", width=4, command=self._browse_batch_file)
        self.browse_batch_btn.pack(side="left", padx=(5, 0))

        # Right Side: Options & Actions
        opts_frame = ttk.Frame(control_card)
        opts_frame.grid(row=1, column=2, sticky="ne", padx=(20, 0), pady=(35, 0))

        # Options
        self.best_quality_var = tk.BooleanVar(value=self.settings.get("best_quality", True))
        ttk.Checkbutton(opts_frame, text="Best Quality (Slower)", variable=self.best_quality_var).pack(anchor="w",
                                                                                                       pady=2)

        timeout_frame = ttk.Frame(opts_frame)
        timeout_frame.pack(anchor="w", pady=2)
        ttk.Label(timeout_frame, text="Timeout: ").pack(side="left")
        self.timeout_var = tk.IntVar(value=self.settings.get("timeout", 20))
        ttk.Spinbox(timeout_frame, from_=5, to=120, textvariable=self.timeout_var, width=5).pack(side="left")
        ttk.Label(timeout_frame, text="s").pack(side="left")

        # Big Buttons
        btn_bar = ttk.Frame(opts_frame)
        btn_bar.pack(fill="x", pady=(15, 0))
        self.start_button = ttk.Button(btn_bar, text="▶ START DOWNLOAD", style="Action.TButton",
                                       command=self.start_process)
        self.start_button.pack(fill="x", pady=2)
        self.cancel_button = ttk.Button(btn_bar, text="⏹ STOP", command=self.cancel_process, state="disabled")
        self.cancel_button.pack(fill="x")

        # 3. Main Content (Split Pane)
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)

        # Left Pane: Queue
        queue_frame = ttk.Frame(self.paned)  # Wrapper
        self.paned.add(queue_frame, weight=2)

        # Queue Header with Progress
        q_header = ttk.Frame(queue_frame)
        q_header.pack(fill="x", pady=(0, 5))
        ttk.Label(q_header, text="Queue", style="SubHeader.TLabel").pack(side="left")

        stats_frame = ttk.Frame(q_header)
        stats_frame.pack(side="right")
        self.timer_label = ttk.Label(stats_frame, text="00:00", style="Mono.TLabel")
        self.timer_label.pack(side="right", padx=5)
        self.counter_label = ttk.Label(stats_frame, text="0/0", font=("Segoe UI", 9, "bold"))
        self.counter_label.pack(side="right", padx=5)

        # Progress Bar
        self.progress_bar = ttk.Progressbar(queue_frame, mode="determinate")
        self.progress_bar.pack(fill="x", pady=(0, 5))

        # Treeview
        cols = ("URL", "Status", "Path")
        self.tree = ttk.Treeview(queue_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("URL", text="Source URL")
        self.tree.heading("Status", text="Status")
        self.tree.heading("Path", text="Filename")
        self.tree.column("URL", width=250)
        self.tree.column("Status", width=100, anchor="center")
        self.tree.column("Path", width=200)

        tree_scroll = ttk.Scrollbar(queue_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        # Tree Actions (Toolbar below tree)
        q_toolbar = ttk.Frame(queue_frame)
        q_toolbar.pack(side="bottom", fill="x", pady=(5, 0))
        self.retry_button = ttk.Button(q_toolbar, text="Retry Failed", command=self._retry_failed, state="disabled")
        self.retry_button.pack(side="left")
        self.clear_button = ttk.Button(q_toolbar, text="Clear All", command=self._clear_batch_list)
        self.clear_button.pack(side="right")

        # Right Pane: Preview & Log
        right_pane = ttk.PanedWindow(self.paned, orient=tk.VERTICAL)
        self.paned.add(right_pane, weight=1)

        # Preview Section
        preview_frame = ttk.LabelFrame(right_pane, text="Preview", padding=10)
        right_pane.add(preview_frame, weight=3)
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.image_label = ttk.Label(preview_frame, text="No Image Selected", anchor="center")
        self.image_label.grid(row=0, column=0, sticky="nsew")

        meta_frame = ttk.Frame(preview_frame)
        meta_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        self.metadata_label = ttk.Label(meta_frame, text="", style="Mono.TLabel", foreground="#888")
        self.metadata_label.pack(side="left")
        self.open_ext_btn = ttk.Button(meta_frame, text="↗ Open", width=6, command=self.open_recent_file,
                                       state="disabled")
        self.open_ext_btn.pack(side="right")

        # Log Section
        log_frame = ttk.LabelFrame(right_pane, text="Event Log", padding=5)
        right_pane.add(log_frame, weight=2)

        self.log_text = tk.Text(log_frame, state="disabled", font=("Consolas", 8), wrap="word", height=8)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        # 4. Status Bar
        status_bar = ttk.Frame(self.root)
        status_bar.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        self.status_label = ttk.Label(status_bar, text="Ready", font=("Segoe UI", 9))
        self.status_label.pack(side="left")

        ttk.Sizegrip(status_bar).pack(side="right")

        # Tags for Colors
        self._configure_tags()

        # Events
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Button-3>", self._on_tree_right_click)
        self._create_context_menu()

    def _configure_tags(self):
        # Adapt colors to theme
        s_fg = "#81C784" if self.is_dark_mode else "#2E7D32"
        f_fg = "#E57373" if self.is_dark_mode else "#C62828"
        p_fg = "#64B5F6" if self.is_dark_mode else "#1565C0"

        self.tree.tag_configure("Success", foreground=s_fg)
        self.tree.tag_configure("Failed", foreground=f_fg)
        self.tree.tag_configure("Searching", foreground=p_fg)

        self.log_text.tag_config("green", foreground=s_fg)
        self.log_text.tag_config("red", foreground=f_fg)
        self.log_text.tag_config("blue", foreground=p_fg)
        self.log_text.tag_config("bold", font=("Consolas", 8, "bold"))

    def _create_context_menu(self):
        self.tree_menu = tk.Menu(self.tree, tearoff=0)
        self.tree_menu.add_command(label="Open File", command=self._ctx_open_file)
        self.tree_menu.add_command(label="Open Folder", command=self._ctx_open_folder)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Copy URL", command=self._ctx_copy_url)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Remove", command=self._ctx_remove_item)

    # --- Logic ---

    def start_process(self):
        save_folder = self.save_location_var.get()
        if not os.path.isdir(save_folder):
            messagebox.showerror("Error", "Invalid save directory.")
            return

        self.cancel_event.clear()

        # Determine Input Mode based on Notebook Tab
        current_tab_idx = self.input_tabs.index(self.input_tabs.select())

        if current_tab_idx == 0:  # Single
            url = self.url_entry.get().strip()
            if not url:
                messagebox.showwarning("Input", "Please enter a URL.")
                self.url_entry.focus()
                return
            self._clear_batch_list()
            self._add_to_batch_list([url])
            self._start_thread()
        else:  # Batch
            fpath = self.batch_file_var.get()
            if not fpath or not os.path.exists(fpath):
                messagebox.showwarning("Input", "Please select a valid batch file.")
                return
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    urls = [line.strip() for line in f if line.strip()]
                if not urls:
                    messagebox.showinfo("Info", "Batch file is empty.")
                    return
                self._clear_batch_list()
                self._add_to_batch_list(urls)
                self._start_thread()
            except Exception as e:
                messagebox.showerror("Error", f"Could not read file: {e}")

    def _start_thread(self):
        self._set_ui_state("RUNNING")
        self._clear_log()
        self._clear_preview()
        self.first_success_previewed = False
        self._batch_start_time = time.time()
        self._tick_timer()
        self.log_message("Starting job...", "blue", bold=True)

        self.active_thread = threading.Thread(target=self._process_wrapper)
        self.active_thread.start()

    def _process_wrapper(self):
        try:
            self._process_batch()
            status = "DONE"
        except Exception as e:
            self.log_message(f"Critical Error: {e}", "red", bold=True)
            status = "DONE"
        finally:
            if self.cancel_event.is_set(): status = "IDLE"
            self.progress_queue.put({"type": "finish_state", "state": status})

    def _process_batch(self):
        items = list(self.batch_items.keys())
        total = len(items)
        save_folder = self.save_location_var.get()
        exts = PRIORITY_EXTENSIONS if self.best_quality_var.get() else EXTENSIONS

        for i, item_id in enumerate(items):
            if self.cancel_event.is_set(): break

            data = self.batch_items[item_id]
            url = data["url"]

            self.progress_queue.put(
                {"type": "tree_update", "id": item_id, "status": "Searching", "tags": ("Searching",)})

            imgur_id = self.extract_imgur_id(url)

            if not imgur_id:
                self.progress_queue.put(
                    {"type": "tree_update", "id": item_id, "status": "Invalid URL", "tags": ("Failed",)})
            else:
                try:
                    # Find URL
                    archive_url, found_ext = self.find_archived_url(imgur_id, exts)
                    # Download
                    fpath = self.save_file(archive_url, save_folder, imgur_id, found_ext)

                    self.most_recent_download = fpath
                    self.progress_queue.put({
                        "type": "tree_update", "id": item_id,
                        "status": "Success", "path": fpath, "tags": ("Success",)
                    })

                    if not self.first_success_previewed:
                        self.progress_queue.put({"type": "preview", "path": fpath})
                        self.first_success_previewed = True

                except Exception as e:
                    self.progress_queue.put(
                        {"type": "tree_update", "id": item_id, "status": str(e), "tags": ("Failed",)})

            self.progress_queue.put({"type": "progress", "value": i + 1, "total": total})

    # --- Core Logic Helpers ---
    def extract_imgur_id(self, url):
        match = re.search(r"(?:i\.)?imgur\.(?:com|io)/(?:a/|gallery/|t/[^/]+/)?([a-zA-Z0-9]{5,7})", url)
        return match.group(1) if match else None

    def find_archived_url(self, imgur_id, exts):
        base = "https://web.archive.org/cdx/search/cdx"
        for ext in exts:
            if self.cancel_event.is_set(): raise Exception("Cancelled")
            params = {"url": f"https://i.imgur.com/{imgur_id}{ext}", "output": "json"}
            try:
                self.log_message(f"Checking {ext}...")
                resp = self.http_session.get(base, params=params, timeout=self.timeout_var.get())
                if resp.status_code == 200:
                    data = resp.json()
                    if len(data) > 1:
                        ts, orig = data[-1][1], data[-1][2]
                        return f"https://web.archive.org/web/{ts}if_/{orig}", ext
            except:
                pass
        raise Exception("Not found in Archive")

    def save_file(self, url, folder, imgur_id, fallback_ext):
        os.makedirs(folder, exist_ok=True)
        with self.http_session.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            chunk = next(r.iter_content(32), None)
            if not chunk: raise Exception("Empty file")

            ext = self._detect_ext(chunk, r.headers.get("Content-Type", ""), fallback_ext)
            path = os.path.join(folder, f"{imgur_id}{ext}")

            # Uniquify
            c = 2
            base = path
            while os.path.exists(path):
                path = f"{base.rsplit('.', 1)[0]}_{c}{ext}"
                c += 1

            with open(path, "wb") as f:
                f.write(chunk)
                shutil.copyfileobj(r.raw, f)
            return path

    def _detect_ext(self, chunk, ctype, fallback):
        if chunk.startswith(b"GIF8"): return ".gif"
        if chunk.startswith(b"\x89PNG"): return ".png"
        if chunk.startswith(b"\xff\xd8"): return ".jpg"
        if b"ftyp" in chunk[:20]: return ".mp4"
        ct = ctype.split(";")[0]
        return MIME_TYPE_MAP.get(ct, fallback)

    # --- UI Updating & Events ---
    def _process_progress_queue(self):
        while not self.progress_queue.empty():
            msg = self.progress_queue.get()
            t = msg.get("type")

            if t == "log":
                self.log_text.config(state="normal")
                self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg['message']}\n",
                                     msg.get("tags", ()))
                self.log_text.see(tk.END)
                self.log_text.config(state="disabled")

            elif t == "tree_update":
                iid = msg["id"]
                vals = list(self.tree.item(iid, "values"))
                vals[1] = msg["status"]
                if "path" in msg: vals[2] = os.path.basename(msg["path"])
                self.tree.item(iid, values=vals, tags=msg.get("tags", ()))

                # Update underlying data
                self.batch_items[iid]["status"] = msg["status"]
                if "path" in msg: self.batch_items[iid]["path"] = msg["path"]

                # Update counters
                s = sum(1 for v in self.batch_items.values() if v["status"] == "Success")
                f = sum(1 for v in self.batch_items.values() if
                        v["status"] not in ("Success", "Queued", "Searching", "Invalid URL"))
                self.counter_label.config(text=f"✓{s}  ✗{f}")

            elif t == "progress":
                self.progress_bar["value"] = msg["value"]
                self.progress_bar["maximum"] = msg["total"]

            elif t == "preview":
                self._update_preview(msg["path"])

            elif t == "finish_state":
                self._set_ui_state(msg["state"])
                self.log_message("Process finished.", "blue", bold=True)

        self.root.after(100, self._process_progress_queue)

    def _set_ui_state(self, state):
        self.app_state = state
        is_idle = state in ("IDLE", "DONE")

        # Inputs
        state_str = "normal" if is_idle else "disabled"
        self.browse_save_btn.config(state=state_str)
        self.browse_batch_btn.config(state=state_str)
        self.start_button.config(state=state_str)
        self.clear_button.config(state=state_str)

        # Stop Button
        self.cancel_button.config(state="normal" if state == "RUNNING" else "disabled")

        # Retry logic
        has_fails = any(v["status"] not in ("Success", "Invalid URL", "Queued") for v in self.batch_items.values())
        self.retry_button.config(state="normal" if (state == "DONE" and has_fails) else "disabled")

        # Open button
        self.open_ext_btn.config(state="normal" if self.most_recent_download else "disabled")

        msgs = {
            "IDLE": "Ready",
            "RUNNING": "Processing...",
            "DONE": "Completed",
            "CANCELLING": "Stopping..."
        }
        self.status_label.config(text=msgs.get(state, "Ready"))

    def _update_preview(self, path):
        try:
            ext = os.path.splitext(path)[1].lower()
            size_str = human_size(os.path.getsize(path))

            if ext in (".jpg", ".png", ".gif"):
                img = Image.open(path)
                w, h = img.size

                # Display logic
                container_w = self.image_label.winfo_width()
                container_h = self.image_label.winfo_height()
                if container_w < 50: container_w = 300  # fallback
                if container_h < 50: container_h = 300

                img.thumbnail((container_w, container_h), Image.Resampling.LANCZOS)
                tk_img = ImageTk.PhotoImage(img)
                self.image_label.configure(image=tk_img, text="")
                self.image_label.image = tk_img  # keep ref
                self.metadata_label.config(text=f"{w}x{h}px | {size_str} | {ext.upper()}")
            else:
                self.image_label.configure(image="", text=f"Preview unavailable for {ext}")
                self.metadata_label.config(text=f"{size_str} | {ext.upper()}")

        except Exception:
            self.image_label.configure(image="", text="Preview Error")

    def _clear_preview(self):
        self.image_label.configure(image="", text="No Image Selected")
        self.image_label.image = None
        self.metadata_label.config(text="")

    def _tick_timer(self):
        if self.app_state == "RUNNING" and self._batch_start_time:
            el = int(time.time() - self._batch_start_time)
            self.timer_label.config(text=f"{el // 60:02d}:{el % 60:02d}")
            self.root.after(1000, self._tick_timer)

    # --- Interaction Handlers ---
    def toggle_theme(self):
        sv_ttk.toggle_theme()
        self.is_dark_mode = sv_ttk.get_theme() == "dark"
        self._init_theme()  # Re-apply winstyles
        self._configure_tags()
        self.theme_btn.config(text="🌗")
        self.settings["theme"] = "dark" if self.is_dark_mode else "light"
        save_settings(self.settings)

    def _browse_save_location(self):
        d = filedialog.askdirectory()
        if d:
            self.save_location_var.set(d)
            self.settings["save_folder"] = d
            save_settings(self.settings)

    def _browse_batch_file(self):
        f = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if f: self.batch_file_var.set(f)

    def cancel_process(self):
        self.cancel_event.set()
        self._set_ui_state("CANCELLING")

    def _retry_failed(self):
        fails = [k for k, v in self.batch_items.items() if v["status"] not in ("Success", "Invalid URL")]
        if not fails: return
        for k in fails:
            self.tree.item(k, values=(self.batch_items[k]["url"], "Queued", ""))
            self.tree.item(k, tags=())
        self._start_thread()

    def _clear_batch_list(self):
        self.tree.delete(*self.tree.get_children())
        self.batch_items.clear()
        self.counter_label.config(text="0/0")
        self.progress_bar["value"] = 0
        self.timer_label.config(text="00:00")

    def _add_to_batch_list(self, urls):
        for u in urls:
            iid = self.tree.insert("", "end", values=(u, "Queued", ""))
            self.batch_items[iid] = {"url": u, "status": "Queued", "path": None}
        self.counter_label.config(text=f"0/0 (Total: {len(urls)})")

    def log_message(self, msg, color=None, bold=False):
        tags = []
        if color: tags.append(color)
        if bold: tags.append("bold")
        self.progress_queue.put({"type": "log", "message": msg, "tags": tuple(tags)})

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

    # --- Window Events ---
    def _on_tree_select(self, _):
        sel = self.tree.selection()
        if sel:
            p = self.batch_items.get(sel[0], {}).get("path")
            if p and os.path.exists(p): self._update_preview(p)

    def _on_tree_double_click(self, _):
        sel = self.tree.selection()
        if sel:
            p = self.batch_items.get(sel[0], {}).get("path")
            if p and os.path.exists(p): webbrowser.open(p)

    def _on_tree_right_click(self, e):
        iid = self.tree.identify_row(e.y)
        if iid:
            self.tree.selection_set(iid)
            self.tree_menu.tk_popup(e.x_root, e.y_root)

    def _ctx_open_file(self):
        sel = self.tree.selection()
        if sel:
            p = self.batch_items.get(sel[0], {}).get("path")
            if p and os.path.exists(p): webbrowser.open(p)

    def _ctx_open_folder(self):
        sel = self.tree.selection()
        if sel:
            p = self.batch_items.get(sel[0], {}).get("path")
            if p: webbrowser.open(os.path.dirname(p))

    def _ctx_copy_url(self):
        sel = self.tree.selection()
        if sel:
            u = self.batch_items.get(sel[0], {}).get("url")
            if u:
                self.root.clipboard_clear()
                self.root.clipboard_append(u)

    def _ctx_remove_item(self):
        sel = self.tree.selection()
        if sel:
            iid = sel[0]
            self.tree.delete(iid)
            del self.batch_items[iid]

    def open_recent_file(self):
        if self.most_recent_download and os.path.exists(self.most_recent_download):
            webbrowser.open(self.most_recent_download)

    def _show_about(self):
        messagebox.showinfo("About", "Imgur Archive Hunter v4.3\nUI Refreshed with SV-TTK")

    def _apply_shortcuts(self):
        self.root.bind("<Control-o>", lambda e: self._browse_batch_file())
        self.root.bind("<Return>", lambda e: self.start_process())

    def _configure_tooltips(self):
        Tooltip(self.browse_save_btn, "Select download folder")
        Tooltip(self.browse_batch_btn, "Select .txt file with URLs")
        Tooltip(self.theme_btn, "Toggle Dark/Light Mode")

    def _restore_initial_state(self):
        if "window_geometry" in self.settings:
            try:
                self.root.geometry(self.settings["window_geometry"])
            except:
                pass
        if "sash" in self.settings:
            try:
                self.paned.sashpos(0, self.settings["sash"])
            except:
                pass

    def _on_window_configure(self, evt):
        if evt.widget == self.root:
            if evt.width != self._last_width or evt.height != self._last_height:
                self._last_width, self._last_height = evt.width, evt.height
                if hasattr(self, "_save_timer"): self.root.after_cancel(self._save_timer)
                self._save_timer = self.root.after(2000, self._save_config)

    def _save_config(self):
        self.settings["window_geometry"] = self.root.geometry()
        try:
            self.settings["sash"] = self.paned.sashpos(0)
        except:
            pass
        self.settings["best_quality"] = self.best_quality_var.get()
        self.settings["timeout"] = self.timeout_var.get()
        save_settings(self.settings)

    def _on_closing(self):
        if self.app_state == "RUNNING":
            if messagebox.askyesno("Exit", "Process running. Stop and exit?"):
                self.cancel_event.set()
                if self.active_thread: self.active_thread.join(1)
                self.root.destroy()
        else:
            self._save_config()
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ImgurArchiveAppV4_5(root)
    root.mainloop()
