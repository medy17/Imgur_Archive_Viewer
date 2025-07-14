import os
import re
import sys
import shutil
import queue
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

import requests
import sv_ttk
from PIL import Image, ImageTk

# --- Handle Optional Imports for Enhanced UX ---
try:
    import darkdetect
except ImportError:
    darkdetect = None

if os.name == 'nt':
    try:
        import pywinstyles
    except ImportError:
        pywinstyles = None
else:
    pywinstyles = None

# --- Constants ---
EXTENSIONS = [".jpg", ".png", ".gif", ".gifv", ".mp4", ".webm", ".mpeg"]
PRIORITY_EXTENSIONS = [".mp4", ".webm", ".gif", ".png", ".jpg", ".mpeg", ".gifv"]
MIME_TYPE_MAP = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
    "video/mp4": ".mp4", "video/webm": ".webm", "video/mpeg": ".mpeg"
}


# --- Application Class ---
class ImgurArchiveAppV4_2:
    def __init__(self, root):
        self.root = root
        self.root.title("Imgur Archive Hunter v4.2")
        self.root.geometry("850x800")
        self.root.minsize(700, 600)

        # --- State & Data Management ---
        self.app_state = 'IDLE'
        self.most_recent_download = None
        self.active_thread = None
        self.cancel_event = threading.Event()
        self.progress_queue = queue.Queue()
        self.batch_items = {}
        self.first_success_previewed = False  # ** NEW: Flag for better UX **

        # --- Theming ---
        if darkdetect and darkdetect.theme():
            initial_theme = darkdetect.theme().lower()
            sv_ttk.set_theme(initial_theme)
            self.is_dark_mode = (initial_theme == "dark")
        else:
            sv_ttk.set_theme("light")
            self.is_dark_mode = False

        self._apply_theme_to_titlebar()

        # --- Core Components ---
        self.http_session = requests.Session()

        # --- UI Initialization ---
        self._create_styles()
        self._create_main_layout()
        self._create_input_frame()
        self._create_batch_view()
        self._create_preview_and_log()
        self._create_status_bar()

        self._set_ui_state('IDLE')
        self.root.after(100, self._process_progress_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ... (Most UI creation methods are unchanged) ...
    def _create_styles(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Header.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Success.TLabel", foreground="green")
        style.configure("Error.TLabel", foreground="red")
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"))
        style.map('Treeview', background=[('selected', '#0078d4')])
        style.configure("Treeview.Heading", font=('Segoe UI', 10, 'bold'))
        style.configure("Success.Treeview", foreground="#008000")
        style.configure("Failed.Treeview", foreground="#E53935")
        style.configure("Searching.Treeview", foreground="#0078d4")

    def _create_main_layout(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=3)
        self.root.rowconfigure(2, weight=2)
        header_frame = ttk.Frame(self.root, padding=(10, 10))
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(header_frame, text="Imgur Archive Hunter", style="Title.TLabel").pack(side="left")
        theme_icon = "☀️" if self.is_dark_mode else "🌙"
        self.theme_button = ttk.Button(header_frame, text=theme_icon, command=self.toggle_theme, width=3)
        self.theme_button.pack(side="right", padx=5)
        ttk.Button(header_frame, text="About", command=self._show_about).pack(side="right")

    def _create_input_frame(self):
        input_container = ttk.LabelFrame(self.root, text="Configuration & Input", padding=10)
        input_container.grid(row=0, column=0, padx=10, pady=(50, 5), sticky="new")
        input_container.columnconfigure(1, weight=1)
        ttk.Label(input_container, text="Save Location:").grid(row=0, column=0, sticky="w", pady=2)
        self.save_location_var = tk.StringVar(value=os.getcwd())
        save_entry = ttk.Entry(input_container, textvariable=self.save_location_var)
        save_entry.grid(row=0, column=1, sticky="ew", padx=5)
        self.browse_save_btn = ttk.Button(input_container, text="...", command=self._browse_save_location, width=3)
        self.browse_save_btn.grid(row=0, column=2, sticky="e")
        self.best_quality_var = tk.BooleanVar(value=True)
        best_quality_check = ttk.Checkbutton(input_container, text="Search for best quality (slower)",
                                             variable=self.best_quality_var)
        best_quality_check.grid(row=1, column=0, columnspan=3, sticky="w", pady=(5, 10))
        ttk.Label(input_container, text="Timeout (s):").grid(row=2, column=0, sticky="w", pady=2)
        self.timeout_var = tk.IntVar(value=20)
        timeout_spinbox = ttk.Spinbox(input_container, from_=5, to_=120, textvariable=self.timeout_var, width=5)
        timeout_spinbox.grid(row=2, column=1, sticky="w", padx=5)
        self.input_mode_var = tk.StringVar(value="single")
        single_radio = ttk.Radiobutton(input_container, text="Single URL", variable=self.input_mode_var, value="single",
                                       command=self._toggle_input_mode)
        single_radio.grid(row=3, column=0, columnspan=3, sticky="w", pady=(15, 2))
        batch_radio = ttk.Radiobutton(input_container, text="Batch from .txt File", variable=self.input_mode_var,
                                      value="batch", command=self._toggle_input_mode)
        batch_radio.grid(row=5, column=0, columnspan=3, sticky="w", pady=(5, 2))
        self.single_url_frame = ttk.Frame(input_container)
        self.single_url_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=20)
        self.url_entry = ttk.Entry(self.single_url_frame)
        self.url_entry.pack(side="left", expand=True, fill="x")
        self.batch_file_frame = ttk.Frame(input_container)
        self.batch_file_var = tk.StringVar()
        batch_entry = ttk.Entry(self.batch_file_frame, textvariable=self.batch_file_var, state="readonly")
        batch_entry.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.browse_batch_btn = ttk.Button(self.batch_file_frame, text="Browse...", command=self._browse_batch_file)
        self.browse_batch_btn.pack(side="left")
        action_frame = ttk.Frame(input_container)
        action_frame.grid(row=7, column=0, columnspan=3, pady=(15, 5))
        self.start_button = ttk.Button(action_frame, text="Start Download", command=self.start_process,
                                       style="Action.TButton")
        self.start_button.pack(side="left", padx=5)
        self.cancel_button = ttk.Button(action_frame, text="Cancel", command=self.cancel_process)
        self.cancel_button.pack(side="left", padx=5)

    def _create_batch_view(self):
        self.batch_frame = ttk.LabelFrame(self.root, text="Batch Process", padding=10)
        self.batch_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.batch_frame.columnconfigure(0, weight=1)
        self.batch_frame.rowconfigure(1, weight=1)
        progress_info_frame = ttk.Frame(self.batch_frame)
        progress_info_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        progress_info_frame.columnconfigure(0, weight=1)
        self.progress_bar = ttk.Progressbar(progress_info_frame, orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        self.progress_label = ttk.Label(progress_info_frame, text="Waiting to start...")
        self.progress_label.grid(row=0, column=1, sticky="w", padx=10)
        batch_actions_frame = ttk.Frame(progress_info_frame)
        batch_actions_frame.grid(row=0, column=2, sticky='e')
        self.retry_button = ttk.Button(batch_actions_frame, text="Retry Failed", command=self._retry_failed)
        self.retry_button.pack(side='left', padx=5)
        self.clear_button = ttk.Button(batch_actions_frame, text="Clear List", command=self._clear_batch_list)
        self.clear_button.pack(side='left')
        cols = ("#0", "URL", "Status", "File Path")
        self.tree = ttk.Treeview(self.batch_frame, columns=cols[1:], show="headings", height=10)
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.heading("URL", text="URL");
        self.tree.heading("Status", text="Status");
        self.tree.heading("File Path", text="File Path")
        self.tree.column("URL", width=300, stretch=True);
        self.tree.column("Status", width=100, anchor="center");
        self.tree.column("File Path", width=300, stretch=True)
        tree_scrollbar = ttk.Scrollbar(self.batch_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.grid(row=1, column=1, sticky="ns")
        self.tree.tag_configure("Success", foreground="#008800" if self.is_dark_mode else "#007700")
        self.tree.tag_configure("Failed", foreground="#FFAAAA" if self.is_dark_mode else "#CC0000")
        self.tree.tag_configure("Searching", foreground="#87CEEB" if self.is_dark_mode else "#0078D4")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def _create_preview_and_log(self):
        paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned_window.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")

        preview_frame = ttk.LabelFrame(paned_window, text="Preview")
        # ** UPDATED: Set a more helpful initial text **
        self.image_label = ttk.Label(preview_frame, anchor="center", text="Select a successful download to preview")
        self.image_label.pack(expand=True, fill="both", padx=5, pady=5)
        paned_window.add(preview_frame, weight=1)

        log_frame = ttk.LabelFrame(paned_window, text="Log")
        log_frame.columnconfigure(0, weight=1);
        log_frame.rowconfigure(0, weight=1)
        log_actions_frame = ttk.Frame(log_frame)
        log_actions_frame.grid(row=1, column=0, sticky='ew')
        ttk.Button(log_actions_frame, text="Export Log...", command=self._export_log).pack(side='right', pady=2)
        self.log_text = tk.Text(log_frame, wrap="word", state="disabled", height=10)
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_scrollbar.set)
        self.log_text.grid(row=0, column=0, sticky="nsew");
        log_scrollbar.grid(row=0, column=1, sticky="ns")
        paned_window.add(log_frame, weight=2)
        self.log_text.tag_config("green", foreground="#4CAF50");
        self.log_text.tag_config("red", foreground="#F44336");
        self.log_text.tag_config("orange", foreground="#FF9800");
        self.log_text.tag_config("blue", foreground="#2196F3");
        self.log_text.tag_config("purple", foreground="#673AB7");
        self.log_text.tag_config("bold", font=("Segoe UI", 9, "bold"))

    def _create_status_bar(self):
        status_bar = ttk.Frame(self.root, padding=(5, 2))
        status_bar.grid(row=3, column=0, sticky="ew")
        self.status_label = ttk.Label(status_bar, text="Ready", anchor="w")
        self.status_label.pack(side="left")
        self.open_file_button = ttk.Button(status_bar, text="Open Last File", command=self.open_recent_file)
        self.open_file_button.pack(side="right", padx=5)
        self.open_folder_button = ttk.Button(status_bar, text="Open Last Folder", command=self.open_recent_folder)
        self.open_folder_button.pack(side="right")

    # --- Core Logic & Processing ---

    def start_process(self):
        # ... (This function is unchanged)
        save_folder = self.save_location_var.get()
        if not os.path.isdir(save_folder):
            messagebox.showerror("Error", "The specified save location is not a valid directory.")
            return
        self.cancel_event.clear()
        if self.input_mode_var.get() == "single":
            url = self.url_entry.get()
            if not url:
                messagebox.showerror("Error", "Please enter an Imgur URL.")
                return
            self._clear_batch_list()
            self._add_to_batch_list([url])
            self._start_process_thread(self._process_batch)
        else:
            file_path = self.batch_file_var.get()
            if not file_path:
                messagebox.showerror("Error", "Please select a batch file.")
                return
            try:
                with open(file_path, "r") as f:
                    urls = [line.strip() for line in f if line.strip()]
                if not urls:
                    messagebox.showinfo("Info", "The selected batch file is empty.")
                    return
                self._clear_batch_list()
                self._add_to_batch_list(urls)
                self._start_process_thread(self._process_batch)
            except FileNotFoundError:
                messagebox.showerror("Error", f"Batch file not found: {file_path}")
                return

    def _start_process_thread(self, target_func, *args):
        # ** UPDATED: Reset preview state on new run **
        self._set_ui_state('RUNNING')
        self._clear_log()
        self._clear_preview()
        self.first_success_previewed = False
        self.log_message("Starting process...", "blue", bold=True)
        self.active_thread = threading.Thread(target=self._process_wrapper, args=(target_func, *args))
        self.active_thread.start()

    def _process_wrapper(self, target_func, *args):
        # ... (This function is unchanged)
        try:
            target_func(*args)
            if not self.cancel_event.is_set():
                self._set_ui_state('DONE')
            else:
                self._set_ui_state('IDLE')
        except Exception as e:
            self.log_message(f"An unexpected critical error occurred: {e}", "red")
            self._set_ui_state('DONE')
        finally:
            self.progress_queue.put({'type': 'status', 'text': 'Process finished.'})

    def _process_batch(self):
        # ** UPDATED: Logic to auto-preview the first success **
        items_to_process = list(self.batch_items.keys())
        total = len(items_to_process)
        save_folder = self.save_location_var.get()
        extensions_to_try = PRIORITY_EXTENSIONS if self.best_quality_var.get() else EXTENSIONS
        mode_msg = "Best Quality" if self.best_quality_var.get() else "Quick Scan"
        self.log_message(f"Starting batch of {total} items with '{mode_msg}' mode.", "purple")

        for i, item_id in enumerate(items_to_process):
            if self.cancel_event.is_set():
                self.log_message("Batch process cancelled by user.", "orange", bold=True)
                break

            url = self.batch_items[item_id]['url']
            self.log_message(f"--- Processing {i + 1}/{total}: {url} ---")
            self.progress_queue.put(
                {'type': 'tree_update', 'id': item_id, 'status': 'Searching', 'tags': ('Searching',)})

            imgur_id = self.extract_imgur_id(url)
            if not imgur_id:
                self.log_message(f"Skipping invalid URL: {url}", "orange")
                self.progress_queue.put(
                    {'type': 'tree_update', 'id': item_id, 'status': 'Invalid URL', 'tags': ('Failed',)})
            else:
                try:
                    file_path = self.download_image(imgur_id, save_folder, extensions_to_try)
                    self.log_message(f"Success! Saved to: {file_path}", "green")
                    self.most_recent_download = file_path
                    self.progress_queue.put(
                        {'type': 'tree_update', 'id': item_id, 'status': 'Success', 'path': file_path,
                         'tags': ('Success',)})

                    # --- AUTO-PREVIEW LOGIC ---
                    if not self.first_success_previewed:
                        self.progress_queue.put({'type': 'preview', 'path': file_path})
                        self.first_success_previewed = True
                except Exception as e:
                    self.log_message(f"Failed for ID {imgur_id}: {e}", "red")
                    self.progress_queue.put(
                        {'type': 'tree_update', 'id': item_id, 'status': str(e), 'tags': ('Failed',)})

            self.progress_queue.put({'type': 'progress', 'value': i + 1, 'total': total})
        else:
            self.log_message("Batch process completed.", "green", bold=True)

    # ... (download_image, find_archived_url, save_file are unchanged) ...
    def download_image(self, imgur_id, save_folder, extensions_to_try):
        archive_url, found_ext = self.find_archived_url(imgur_id, extensions_to_try)
        try:
            file_path = self.save_file(archive_url, save_folder, imgur_id, fallback_ext=found_ext)
            return file_path
        except PermissionError:
            raise Exception("Permission denied to save file.")
        except requests.RequestException as e:
            raise Exception(f"Network error during download: {e}")

    def find_archived_url(self, imgur_id, extensions_to_try):
        base_url = "https://web.archive.org/cdx/search/cdx"
        for ext in extensions_to_try:
            if self.cancel_event.is_set(): raise Exception("Operation cancelled.")
            query_url = f"https://i.imgur.com/{imgur_id}{ext}"
            params = {"url": query_url, "output": "json"}
            self.log_message(f"Checking for {ext}...")
            try:
                response = self.http_session.get(base_url, params=params, timeout=self.timeout_var.get())
                response.raise_for_status()
                data = response.json()
                if len(data) > 1:
                    timestamp, original_url = data[-1][1], data[-1][2]
                    archive_url = f"https://web.archive.org/web/{timestamp}if_/{original_url}"
                    self.log_message(f"Found archived version with {ext}", "green")
                    return archive_url, ext
            except requests.RequestException:
                self.log_message(f"Network issue or timeout for {ext}.", "orange")
                continue
        raise Exception("No archived versions found.")

    def save_file(self, url, folder, imgur_id, fallback_ext):
        os.makedirs(folder, exist_ok=True)
        with self.http_session.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            first_chunk = next(r.iter_content(chunk_size=32), None)
            if not first_chunk: raise Exception("Downloaded file is empty.")
            ext = self._get_file_extension(first_chunk, r.headers.get("Content-Type", ""), fallback_ext)
            base_filename = os.path.join(folder, imgur_id)
            output_path = f"{base_filename}{ext}"
            counter = 2
            while os.path.exists(output_path):
                output_path = f"{base_filename}_{counter}{ext}"
                counter += 1
            with open(output_path, "wb") as f:
                f.write(first_chunk)
                shutil.copyfileobj(r.raw, f)
            return output_path

    # --- UI State & Event Handlers ---
    # ... (Most of this section is unchanged) ...
    def _set_ui_state(self, new_state):
        self.app_state = new_state
        is_idle = (new_state == 'IDLE' or new_state == 'DONE')
        is_running = (new_state == 'RUNNING')
        for widget in [self.browse_save_btn, self.url_entry, self.browse_batch_btn]:
            widget.config(state="normal" if is_idle else "disabled")
        self.start_button.config(state="normal" if is_idle else "disabled")
        self.cancel_button.config(state="normal" if is_running else "disabled")
        self.retry_button.config(state='disabled')
        if new_state == 'DONE':
            if any(item['status'] not in ('Success', 'Invalid URL') for item in self.batch_items.values()):
                self.retry_button.config(state='normal')
        self.clear_button.config(state="normal" if is_idle else "disabled")
        self.open_file_button.config(state="normal" if self.most_recent_download else "disabled")
        self.open_folder_button.config(state="normal" if self.most_recent_download else "disabled")
        status_messages = {'IDLE': 'Ready.', 'RUNNING': 'Processing... Please wait.',
                           'CANCELLING': 'Cancellation requested...', 'DONE': 'Process finished.'}
        self.status_label.config(text=status_messages.get(new_state, 'Unknown state.'))

    def _process_progress_queue(self):
        try:
            while not self.progress_queue.empty():
                msg = self.progress_queue.get_nowait()
                msg_type = msg.get('type')
                if msg_type == 'log':
                    self.log_text.config(state="normal")
                    self.log_text.insert(tk.END, msg['message'] + "\n", msg.get('tags', ()))
                    self.log_text.see(tk.END)
                    self.log_text.config(state="disabled")
                elif msg_type == 'status':
                    self.status_label.config(text=msg['text'])
                elif msg_type == 'progress':
                    self.progress_bar['value'] = msg['value'];
                    self.progress_bar['maximum'] = msg['total']
                    self.progress_label.config(text=f"{msg['value']}/{msg['total']}")
                elif msg_type == 'preview':
                    self._update_preview(msg['path'])
                elif msg_type == 'tree_update':
                    item_id = msg['id']
                    self.tree.item(item_id,
                                   values=(self.batch_items[item_id]['url'], msg['status'], msg.get('path', '')))
                    self.tree.item(item_id, tags=msg.get('tags', ()))
                    self.batch_items[item_id]['status'] = msg['status']
                    if 'path' in msg: self.batch_items[item_id]['path'] = msg['path']
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._process_progress_queue)

    def cancel_process(self):
        if self.active_thread and self.active_thread.is_alive():
            self._set_ui_state('CANCELLING')
            self.cancel_event.set()
            self.log_message("Cancellation signal sent. Waiting for current task to finish...", "orange", bold=True)

    def _on_closing(self):
        if self.app_state == 'RUNNING':
            if messagebox.askyesno("Confirm Exit", "A process is currently running. Are you sure you want to exit?"):
                self.cancel_event.set()
                if self.active_thread: self.active_thread.join(timeout=2)
                self.root.destroy()
        else:
            self.root.destroy()

    # --- Helper & Utility Methods ---
    # ... (most helpers unchanged) ...
    def log_message(self, message, color_tag=None, bold=False):
        tags = []
        if color_tag: tags.append(color_tag)
        if bold: tags.append("bold")
        self.progress_queue.put({'type': 'log', 'message': message, 'tags': tuple(tags)})

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

    def _get_file_extension(self, data_chunk, content_type_header, fallback_ext):
        if data_chunk.startswith(b"GIF8"): return ".gif"
        if data_chunk.startswith(b"\x89PNG\r\n\x1a\n"): return ".png"
        if data_chunk.startswith(b"\xff\xd8\xff"): return ".jpg"
        if b"ftyp" in data_chunk[:16]: return ".mp4"
        ct = content_type_header.split(";")[0]
        if ct in MIME_TYPE_MAP:
            self.log_message(f"Using server content-type. Saving as '{MIME_TYPE_MAP[ct]}'.", "blue")
            return MIME_TYPE_MAP[ct]
        self.log_message(f"Could not determine type. Using fallback extension: '{fallback_ext}'.", "orange")
        return fallback_ext

    @staticmethod
    def extract_imgur_id(url):
        match = re.search(r"(?:i\.)?imgur\.(?:com|io)/(?:a/|gallery/|t/[^/]+/)?([a-zA-Z0-9]{5,7})", url)
        return match.group(1) if match else None

    # ** COMPLETELY REWRITTEN AND FIXED **
    def _update_preview(self, file_path):
        """Generates and displays a thumbnail for the given image file path."""
        try:
            ext = os.path.splitext(file_path)[-1].lower()
            if ext in [".jpg", ".png", ".gif"]:
                image = Image.open(file_path)

                # Use a fixed max size for robust thumbnailing
                max_size = (350, 350)
                image.thumbnail(max_size, Image.Resampling.LANCZOS)

                tk_image = ImageTk.PhotoImage(image)
                self.image_label.config(image=tk_image, text="")
                # CRITICAL: Keep a reference to the image to prevent garbage collection
                self.image_label.image = tk_image
            else:
                self.image_label.config(image="", text=f"Preview not available\nfor {ext} files.")
                # Clear the reference if it's not an image
                self.image_label.image = None
        except Exception as e:
            self.log_message(f"Error updating preview: {e}", "red")
            self.image_label.config(image="", text="Error loading preview.")
            self.image_label.image = None

    def _clear_preview(self):
        """Resets the preview area to its default state."""
        self.image_label.config(image="", text="Select a successful download to preview")
        self.image_label.image = None

    def _retry_failed(self):
        # ... (This function is unchanged) ...
        failed_items = [iid for iid, data in self.batch_items.items() if
                        data['status'] not in ('Success', 'Invalid URL')]
        if not failed_items:
            messagebox.showinfo("Info", "No failed items to retry.")
            return
        for iid in failed_items:
            self.tree.item(iid, values=(self.batch_items[iid]['url'], "Queued", ""));
            self.tree.item(iid, tags=())
        self.batch_items = {iid: self.batch_items[iid] for iid in failed_items}
        self.first_success_previewed = False  # Reset for the new run
        self._start_process_thread(self._process_batch)

    def _clear_batch_list(self):
        # ... (This function is unchanged) ...
        for item in self.tree.get_children(): self.tree.delete(item)
        self.batch_items.clear();
        self.progress_bar['value'] = 0
        self.progress_label.config(text="Waiting to start...");
        self.retry_button.config(state='disabled')

    def _add_to_batch_list(self, urls):
        # ... (This function is unchanged) ...
        for url in urls:
            item_id = self.tree.insert("", "end", values=(url, "Queued", ""))
            self.batch_items[item_id] = {'url': url, 'status': 'Queued', 'path': None}

    def _on_tree_select(self, event):
        # ... (This function is unchanged) ...
        selected_items = self.tree.selection()
        if not selected_items: return
        item_id = selected_items[0]
        item_data = self.batch_items.get(item_id)
        if item_data and item_data.get('path'): self._update_preview(item_data['path'])

    # --- Button & Menu Callbacks ---
    # ... (This section is mostly unchanged) ...
    def _apply_theme_to_titlebar(self):
        if pywinstyles is None: return
        try:
            hwnd = pywinstyles.get_hwnd(self.root)
            version = sys.getwindowsversion()
            is_dark = sv_ttk.get_theme() == "dark"
            if version.major == 10 and version.build >= 22000:
                header_color = "#1c1c1c" if is_dark else "#fafafa"
                pywinstyles.change_header_color(hwnd, header_color)
            elif version.major == 10:
                pywinstyles.apply_style(self.root, "dark" if is_dark else "normal")
                self.root.wm_attributes("-alpha", 0.99);
                self.root.wm_attributes("-alpha", 1.0)
        except Exception as e:
            print(f"Could not apply style to title bar: {e}")

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        theme_to_set = "dark" if self.is_dark_mode else "light"
        sv_ttk.set_theme(theme_to_set)
        self._apply_theme_to_titlebar()
        self.theme_button.config(text="☀️" if self.is_dark_mode else "🌙")
        self.tree.tag_configure("Success", foreground="#66BB6A" if self.is_dark_mode else "#007700")
        self.tree.tag_configure("Failed", foreground="#EF5350" if self.is_dark_mode else "#CC0000")
        self.tree.tag_configure("Searching", foreground="#42A5F5" if self.is_dark_mode else "#0078D4")

    def _toggle_input_mode(self):
        if self.input_mode_var.get() == "single":
            self.batch_file_frame.grid_forget()
            self.single_url_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=20)
            self.start_button.config(text="Start Download")
        else:
            self.single_url_frame.grid_forget()
            self.batch_file_frame.grid(row=6, column=0, columnspan=3, sticky="ew", padx=20)
            self.start_button.config(text="Start Batch")

    def _browse_save_location(self):
        folder = filedialog.askdirectory(initialdir=self.save_location_var.get())
        if folder: self.save_location_var.set(folder)

    def _browse_batch_file(self):
        file_path = filedialog.askopenfilename(title="Select .txt File", filetypes=[("Text Files", "*.txt")])
        if file_path: self.batch_file_var.set(file_path)

    def open_recent_file(self):
        if self.most_recent_download and os.path.exists(self.most_recent_download):
            webbrowser.open(self.most_recent_download)
        else:
            messagebox.showwarning("Warning", "File not found or no successful download yet.")

    def open_recent_folder(self):
        if self.most_recent_download and os.path.exists(self.most_recent_download):
            webbrowser.open(os.path.dirname(self.most_recent_download))
        else:
            messagebox.showwarning("Warning", "File location not available.")

    def _export_log(self):
        log_content = self.log_text.get("1.0", tk.END)
        if not log_content.strip(): messagebox.showinfo("Info", "Log is empty, nothing to export."); return
        filename = filedialog.asksaveasfilename(defaultextension=".txt",
                                                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                                                title="Save Log As",
                                                initialfile=f"imgur_hunter_log_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt")
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                messagebox.showinfo("Success", f"Log successfully exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export log: {e}")

    def _show_about(self):
        about_text = ("Imgur Archive Hunter v4.2\n\n"
                      "This application searches the Wayback Machine's CDX index to find and download archived Imgur media.\n\n"
                      "Features:\n"
                      "- Single URL or Batch .txt file processing\n"
                      "- 'Best Quality' mode prioritizes video/GIF\n"
                      "- Real-time progress tracking & retry failed\n"
                      "- Auto-detects system theme on startup\n"
                      "- Dark mode title bar on Windows 10/11\n"
                      "- Fixed and improved image preview system\n\n"
                      "UI theme powered by sv-ttk.")
        messagebox.showinfo("About Imgur Archive Hunter", about_text)


if __name__ == "__main__":
    root = tk.Tk()
    app = ImgurArchiveAppV4_2(root)
    root.mainloop()