# Imgur Archive Viewer

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-CC--BY--NC%204.0-green.svg)
![Status](https://img.shields.io/badge/status-active-brightgreen.svg)

A modern, feature-rich desktop application for finding and downloading lost or deleted media from Imgur's history on the Internet Archive's Wayback Machine.

---

<p align="center">
  <!-- IMPORTANT: Replace this with a screenshot or GIF of your v4.1 application! -->
  <img src="https://i.imgur.com/qMUujbP.png" alt="Imgur Archive Viewer Screenshot" width="700"/>
</p>

---

## Overview

**Imgur Archive Viewer** is a powerful tool built with Python and Tkinter that queries the Wayback Machine's CDX API to find and recover archived Imgur media. With a sleek, modern UI powered by `sv-ttk`, it provides a seamless user experience, including automatic dark/light mode detection and robust batch processing capabilities.

If an Imgur link is dead but you suspect it was once archived, this is the tool to find it.

## Key Features

- **Modern User Interface**: A clean, professional-looking UI with automatic light/dark theme detection that matches your OS settings.
- **Robust Batch Processing**:
    - Process hundreds of URLs from a `.txt` file.
    - View real-time status for each URL (Queued, Searching, Success, Failed) in an interactive list.
- **Retry Failed Downloads**: A "Retry Failed" button conveniently re-queues only the items that failed in the last batch.
- **Intelligent Search Modes**:
    - **Best Quality (Default)**: Slower, prioritized search that finds videos (`.mp4`, `.webm`) over static thumbnails (`.jpg`).
    - **Quick Scan**: Faster search that finds any available version, prioritizing speed.
- **Interactive Preview**: Click on a successfully downloaded item in the batch list to see an image preview directly within the app.
- **Configurable Settings**: Easily adjust the save location and network request timeout directly from the UI.
- **Comprehensive Logging**:
    - See a detailed, color-coded log of the entire process.
    - Export the session log to a `.txt` file for record-keeping.
- **Standalone Executable**: Comes with instructions to build a single `.exe` file for easy distribution on Windows.

## Requirements

- **Python**: Version 3.8 or higher.
- **Dependencies**: The application relies on several external libraries.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/Imgur_Archive_Viewer_Repo.git
    cd Imgur_Archive_Viewer_Repo
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    # On Windows
    python -m venv .venv
    .\.venv\Scripts\activate

    # On macOS/Linux
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install the required dependencies from `requirements.txt`:**
    ```bash
    pip install -r requirements.txt
    ```

## How to Use

1.  **Launch the Application**:
    ```bash
    python imgur_archive_viewer_v4.1.py
    ```

2.  **Configure Settings**:
    - **Save Location**: Browse to the folder where you want files to be saved.
    - **Search Quality**: Check the box for "Best Quality" mode (slower but recommended) or uncheck it for a faster scan.
    - **Timeout**: Adjust the network timeout if you are on a slow connection.

3.  **Choose an Input Mode**:

    - **For a Single URL**:
        1. Select the "Single URL" radio button.
        2. Paste the full Imgur URL into the entry box.
        3. Click **"Start Download"**.

    - **For Batch Processing**:
        1. Create a `.txt` file where each line is a different Imgur URL.
        2. Select the "Batch from .txt File" radio button.
        3. Click "Browse..." to select your `.txt` file.
        4. Click **"Start Batch"**.

4.  **Monitor Progress**:
    - Watch the **Batch Process** list update with the status of each URL.
    - Observe detailed logs in the **Log** panel.
    - The progress bar will show the overall completion of the batch.

5.  **Post-Processing**:
    - Click **"Retry Failed"** to re-attempt downloads for any URLs that errored out.
    - Click on a successful item in the list to see its preview.
    - Use the **"Open Last File"** and **"Open Last Folder"** buttons for quick access to your downloads.

## Building a Windows Executable (`.exe`)

You can create a standalone `.exe` file using PyInstaller.

1.  **Install PyInstaller**:
    ```bash
    pip install pyinstaller
    ```

2.  **Provide an Icon (Optional)**: Place an icon file (e.g., `app_icon.ico`) in the project's root directory.

3.  **Run the Build Command**: The `sv-ttk` library requires its data files to be bundled explicitly. Use the following command, replacing `<path_to_sv_ttk>` with the actual path on your system.

    > **Tip**: To find the path, run `python -c "import sv_ttk, os; print(os.path.dirname(sv_ttk.__file__))"` in your activated virtual environment.

    ```bash
    pyinstaller --onefile --windowed --icon="app_icon.ico" --add-data="<path_to_sv_ttk>;sv_ttk" imgur_archive_viewer_v4.1.py
    ```
    *Example Path:* `--add-data="C:\Users\YourUser\...\.venv\Lib\site-packages\sv_ttk;sv_ttk"`

4.  **Find your application** in the `dist` folder. It is now a portable executable.

## License

This project is released under the Attribution-NonCommercial 4.0 International License (CC BY-NC-SA). You are free to use, modify, and distribute it as long as appropriate credit is given.
## Contributing

Contributions, issues, and feature requests are welcome. Feel free to check the [issues page](https://github.com/your-username/Imgur_Archive_Viewer_Repo/issues) if you want to contribute.

---