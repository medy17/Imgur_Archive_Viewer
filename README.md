## Overview

The **Imgur Archive Viewer** is a Python-based desktop application designed to assist users in retrieving and viewing archived images from Imgur. The application leverages the Wayback Machine (Internet Archive) to locate and download images, making it especially useful for retrieving images that may no longer be available on Imgur directly.

This application supports a wide range of image and video file formats, offering a clean graphical user interface (GUI) built with Tkinter.

---
### New in v2:

- **Batch Processing**: Process multiple Imgur URLs at once from a `.txt` file.
- **Enhanced Folder Management**: Automatically organizes downloads, even during batch processing.

---
### How to Batch Process
- Paste links in a `.txt` file separated by a line break.
- Save as the file as a `.txt`. No other extension will work (eg `.rtf`, `.docx`, `.pdf` etc)
- Load up Imgur_Archive_ViewerV2.py then select `Batch Process from File`.
- The app will automatically create folders for every image and will update you on the progress within the GUI.

---

## Features

- **URL-Based Retrieval**: Input an Imgur URL, and the application will search for archived versions.
- **Multiple File Formats**: Supports common extensions like `.jpg`, `.png`, `.gif`, `.mp4`, `.webm`, and more.
- **Extension Selection**: Users can select which file types they want to retrieve.
- **Archived File Retrieval**: Integrates with the Wayback Machine to search for and download archived images.
- **Image Preview**: View the most recently downloaded image directly in the app.
- **Folder Management**: Automatically organizes downloaded files into folders to prevent clutter.
- **Error Handling**: Displays clear error messages if issues arise during URL processing or image retrieval.

---

## Requirements

- **Python**: Version 3.8 or higher.
- **Dependencies**:
    - `requests`
    - `opencv-python`
    - `pillow`
    - `tkinter` (pre-installed with Python on most systems)

To install missing dependencies, run:

```bash
pip install -r requirements.txt
```

---

## How to Use

1. **Launch the Application**: Run the script in your terminal:
    ```bash
    python imgur_archive_viewerV2.py
    ```
2. **Enter the Imgur URL**:
    - Copy and paste the desired Imgur URL into the text input field labeled **"Imgur URL"**.
3. **Select File Extensions**:
    - Choose the file types you want the application to retrieve (e.g., `.jpg`, `.png`).
4. **Submit and Save**:
    - Click **"Submit New"** to start the process.
    - Select a folder where you want the downloaded images to be saved.
5. **View Downloaded Image**:
    - Use the **"Open Most Recent Download"** button to preview the most recently downloaded file in the app.
6. **Handle Existing Folders**:
    - If a folder with the same name already exists, the application appends a suffix (`_2`) to avoid overwriting and warns you that a folder for the image already exists in the directory.

---

## Key Functionalities

### 1. **Image Retrieval**:

- The app uses the **Wayback Machine's CDX API** to locate archived versions of Imgur-hosted images.
- Automatically tries each selected extension until a valid archived version is found.

### 2. **Download and Save**:

- Downloads the located file from the archive and saves it in the specified folder.
- Files are named using the Imgur ID, with an optional suffix to handle duplicates.

### 3. **Image Display**:

- Supports displaying `.jpg`, `.jpeg`, and `.png` images within the GUI.
- Resizes large images to fit the application window.

---

## Error Handling

- **Invalid URL**: Prompts users to enter a valid Imgur URL.
- **Unsupported Extensions**: Alerts users if the provided URL has an unsupported extension.
- **No Archive Found**: Notifies users if no archived versions are available for the given file types.
- **Download Issues**: Displays an error message if downloading the file fails.

---

## Customization

You can modify the following variables in the script:

- **`EXTENSIONS`**: To add or remove supported file types.
- **GUI Dimensions**: Adjust the default window size by changing the `self.root.geometry("500x500")` line in the `__init__` method.

---

## Troubleshooting

- **Missing Dependencies**: Ensure all required Python packages are installed.
- **Permission Errors**: Run the script as an administrator or save files in a directory where you have write permissions.
- **Display Issues**: Ensure OpenCV (`opencv-python`) and Pillow (`pillow`) are installed to support image processing and display.

---

## Future Enhancements

- Extend support for `.gif`, `.gifv`, `.mp4` previews in the app window.

---

## License

This project is released under the Attribution-NonCommercial 4.0 International License (CC BY-NC-SA). You are free to use, modify, and distribute it as long as appropriate credit is given.

---

## Contact

For questions or feedback, please create an issue or reach out to the developer via GitHub.
