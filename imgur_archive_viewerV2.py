import os
import threading
import requests
import tkinter as tk
from tkinter import ttk, filedialog
import shutil
import queue
import cv2

# Extensions to try
EXTENSIONS = [".jpg", ".png", ".gif", ".gifv", ".mp4", ".webm", ".mpeg"]


class ImgurArchiveApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Imgur Archive")
        self.root.geometry("500x500")
        self.root.resizable(True, True)

        # URL Input
        self.url_label = tk.Label(root, text="Imgur URL:")
        self.url_label.pack(pady=5)
        self.url_entry = tk.Entry(root, width=50)
        self.url_entry.pack(pady=5)

        # Extension Selection
        self.extension_label = tk.Label(root, text="Select Extensions:")
        self.extension_label.pack(pady=5)

        # Dropdown for Extensions
        self.check_vars = {ext: tk.BooleanVar(value=True) for ext in EXTENSIONS}
        self.extension_frame = ttk.LabelFrame(root, text="Extensions")
        self.extension_frame.pack(pady=5)
        for ext, var in self.check_vars.items():
            chk = tk.Checkbutton(self.extension_frame, text=ext, variable=var)
            chk.pack(anchor="w")

        # Submit Button
        self.submit_button = tk.Button(root, text="Submit New", command=self.start_process)
        self.submit_button.pack(pady=5)

        # Batch Process Button
        self.batch_button = tk.Button(root, text="Batch Process from File", command=self.start_batch_process)
        self.batch_button.pack(pady=5)

        # Open Recent Button
        self.open_recent_button = tk.Button(root, text="Open Most Recent Download", command=self.open_recent_download)
        self.open_recent_button.pack(pady=5)

        # Status Label
        self.status_label = tk.Label(root, text="", fg="blue")
        self.status_label.pack(pady=5)

        # Warning Label for Existing Folders
        self.warning_label = tk.Label(root, text="", fg="red")
        self.warning_label.pack(pady=5)

        # Create a frame for the image to control its position and size
        self.image_frame = tk.Frame(root, width=500, height=500)
        self.image_frame.pack(expand=True, fill="both", pady=10)

        # Image Label inside the frame
        self.image_canvas = tk.Label(self.image_frame)
        self.image_canvas.pack(expand=True)

        # Track Most Recent Download
        self.most_recent_download = None

        # Queue for Progress Updates
        self.progress_queue = queue.Queue()

    def start_process(self):
        """Start the URL processing in a separate thread."""
        self.status_label.config(text="Starting process...", fg="blue")
        thread = threading.Thread(target=self.process_url)
        thread.start()
        self.root.after(100, self.check_progress)  # Periodically check the queue for updates

    def start_batch_process(self):
        """Start batch processing of URLs from a .txt file."""
        file_path = filedialog.askopenfilename(title="Select .txt File", filetypes=[("Text Files", "*.txt")])
        if not file_path:
            self.status_label.config(text="No file selected.", fg="red")
            return

        save_folder = filedialog.askdirectory(title="Select Batch Process Folder")
        if not save_folder:
            self.status_label.config(text="No folder selected.", fg="red")
            return

        self.status_label.config(text="Starting batch process...", fg="blue")
        thread = threading.Thread(target=self.process_batch, args=(file_path, save_folder))
        thread.start()
        self.root.after(100, self.check_progress)  # Periodically check the queue for updates

    def check_progress(self):
        """Check the queue for progress updates and update the GUI."""
        try:
            while not self.progress_queue.empty():
                message, color = self.progress_queue.get_nowait()
                self.status_label.config(text=message, fg=color)
        except queue.Empty:
            pass
        self.root.after(100, self.check_progress)  # Continue checking

    def process_batch(self, file_path, save_folder):
        """Process each URL in the provided .txt file."""
        with open(file_path, "r") as f:
            urls = [line.strip() for line in f if line.strip()]

        total_urls = len(urls)
        for index, url in enumerate(urls, start=1):
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, url)
            self.process_url_batch(url, save_folder)
            self.progress_queue.put((f"Processed {index}/{total_urls} URLs.", "blue"))

    def process_url_batch(self, imgur_url, save_folder):
        """Process a single URL and save to a specific folder."""
        self.warning_label.config(text="")  # Clear warnings
        if not imgur_url:
            self.progress_queue.put(("Invalid Imgur URL.", "red"))
            return

        # Extract Image ID and check if an extension exists in the URL
        url_parts = imgur_url.split("/")[-1]
        imgur_id, ext_in_url = os.path.splitext(url_parts)

        # Validate the file extension if it exists
        if ext_in_url and ext_in_url.lower() not in EXTENSIONS:
            self.progress_queue.put(("Invalid file extension in the URL.", "red"))
            return

        selected_extensions = [ext for ext, var in self.check_vars.items() if var.get()]

        if not selected_extensions:
            self.progress_queue.put(("No extensions selected.", "red"))
            return

        # If the URL has an extension, prioritize using it
        if ext_in_url:
            selected_extensions = [ext_in_url]

        # Create folder for each image
        image_folder = os.path.join(save_folder, imgur_id)
        file_suffix = ""
        if os.path.exists(image_folder):
            file_suffix = "_2"

        try:
            archive_url, ext = self.get_archived_image_url(imgur_id, selected_extensions)
            file_path = self.download_and_save_image(archive_url, image_folder, imgur_id, ext, file_suffix)
            self.most_recent_download = file_path  # Track most recent download
            self.progress_queue.put((f"Image saved successfully: {file_path}", "green"))
        except Exception as e:
            self.progress_queue.put((f"Error: {e}", "red"))

    def process_url(self):
        self.warning_label.config(text="")  # Clear warnings
        imgur_url = self.url_entry.get()
        if not imgur_url:
            self.progress_queue.put(("Please enter a valid Imgur URL.", "red"))
            return

        # Extract Image ID and check if an extension exists in the URL
        url_parts = imgur_url.split("/")[-1]
        imgur_id, ext_in_url = os.path.splitext(url_parts)

        # Validate the file extension if it exists
        if ext_in_url and ext_in_url.lower() not in EXTENSIONS:
            self.progress_queue.put(("Invalid file extension in the URL.", "red"))
            return

        selected_extensions = [ext for ext, var in self.check_vars.items() if var.get()]

        if not selected_extensions:
            self.progress_queue.put(("Please select at least one extension.", "red"))
            return

        # Create folder in current working directory if no folder selected
        save_folder = os.getcwd()
        image_folder = os.path.join(save_folder, imgur_id)
        file_suffix = ""
        if os.path.exists(image_folder):
            self.warning_label.config(
                text=f"Warning: Folder '{imgur_id}' already exists. Saving as a new file."
            )
            file_suffix = "_2"

        try:
            archive_url, ext = self.get_archived_image_url(imgur_id, selected_extensions)
            file_path = self.download_and_save_image(archive_url, image_folder, imgur_id, ext, file_suffix)
            self.most_recent_download = file_path  # Track most recent download
            self.progress_queue.put((f"Image saved successfully: {file_path}", "green"))
        except Exception as e:
            self.progress_queue.put((f"Error: {e}", "red"))

    def get_archived_image_url(self, imgur_id, extensions):
        """Attempt to retrieve archived image from the CDX API for each extension."""
        base_url = "https://web.archive.org/cdx/search/cdx"
        for ext in extensions:
            query_url = f"https://i.imgur.com/{imgur_id}{ext}"
            query_params = {"url": f"i.imgur.com/{imgur_id}{ext}", "output": "json"}

            # Update progress
            self.progress_queue.put((f"Trying {query_url}...", "blue"))

            response = requests.get(base_url, params=query_params)
            if response.status_code == 200:
                data = response.json()
                if len(data) > 1:  # Found at least one archive
                    timestamp = data[1][1]
                    original_url = data[1][2]
                    archive_url = f"https://web.archive.org/web/{timestamp}/{original_url}"
                    return archive_url, ext

        raise ValueError("No archived versions found for the selected extensions.")

    def download_and_save_image(self, archive_url, save_folder, imgur_id, ext, file_suffix):
        """Download and save the retrieved image to a folder."""
        response = requests.get(archive_url, stream=True)
        if response.status_code == 200:
            # Create a folder for the image
            os.makedirs(save_folder, exist_ok=True)

            # Save the file with suffix if needed
            file_name = f"{imgur_id}{file_suffix}{ext}"
            file_path = os.path.join(save_folder, file_name)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(response.raw, f)

            return file_path
        else:
            raise ValueError("Failed to download the archived image.")

    def open_recent_download(self):
        """Display the most recent download in the Tkinter window."""
        if self.most_recent_download and os.path.exists(self.most_recent_download):
            try:
                ext = os.path.splitext(self.most_recent_download)[-1].lower()
                if ext in [".jpg", ".png", ".gif"]:
                    # Read the image using OpenCV
                    image = cv2.imread(self.most_recent_download)

                    if image is not None:
                        # Resize the image to fit within a maximum size
                        max_size = (300, 300)
                        height, width = image.shape[:2]
                        scaling_factor = min(max_size[0] / width, max_size[1] / height, 1)
                        new_dimensions = (int(width * scaling_factor), int(height * scaling_factor))
                        resized_image = cv2.resize(image, new_dimensions, interpolation=cv2.INTER_AREA)

                        # Convert from BGR to RGB for Tkinter
                        rgb_image = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)

                        # Convert to PhotoImage format
                        from PIL import Image, ImageTk
                        pil_image = Image.fromarray(rgb_image)
                        tk_image = ImageTk.PhotoImage(pil_image)

                        # Update the image in the GUI
                        self.image_canvas.configure(image=tk_image)
                        self.image_canvas.image = tk_image  # Keep a reference!
                        self.status_label.config(text="Displayed latest image.", fg="green")
                    else:
                        self.status_label.config(text="Error loading image.", fg="red")
                else:
                    self.status_label.config(text="Cannot display this file type.", fg="red")
            except Exception as e:
                self.status_label.config(text=f"Error displaying file: {str(e)}", fg="red")
        else:
            self.status_label.config(text="No recent download to display or file not found.", fg="red")

# Run the Application
if __name__ == "__main__":
    root = tk.Tk()
    app = ImgurArchiveApp(root)
    root.mainloop()
