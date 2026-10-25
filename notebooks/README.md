# Content Engine — Free Google Colab Guide

This guide explains how to run the Content Engine notebook in Google Colab for free, without installing anything on your computer or providing a payment card.

## What it does

The notebook takes a YouTube URL (for a video you own or are authorized to process) and produces three real, downloadable vertical MP4 clips:

- 20 seconds at 1080x1920 with burned-in captions
- 30 seconds at 1080x1920 with burned-in captions
- 35 seconds at 1080x1920 with burned-in captions

All clips use H.264 video, AAC audio, and are rendered by the project's real FFmpeg renderer.

## What you need

- A Google account (free)
- A YouTube URL for a video you own or are authorized to process (must be at least 40 seconds long)
- A web browser (Chrome, Firefox, Safari, or Edge)

That's it. No payment card, no local software install, no API keys.

## Step-by-step instructions

### Step 1: Get the project files

Download the Content Engine project as a ZIP file to your computer. If you received this project as a folder, compress the entire folder into a ZIP file.

### Step 2: Open Google Colab

Go to [https://colab.research.google.com](https://colab.research.google.com) in your browser and sign in with your Google account.

### Step 3: Upload the notebook

1. Click **File** in the top menu, then **Upload notebook**.
2. Click **Choose File** and select `Content_Engine_Free.ipynb` from the `notebooks/` folder.
3. The notebook opens in a new Colab tab.

### Step 4: Upload the project code

1. Click the **folder icon** in the left sidebar.
2. Click the **upload** button (the icon with an arrow pointing up).
3. Upload the project ZIP file you created in Step 1.
4. After it uploads, right-click the ZIP file and select **Extract to /content/**.
5. Make sure the extracted folder contains a `backend/app/` directory. If it extracted to a different name, that's fine — Cell 2 will search for it automatically.

### Step 5: Run the notebook

Run each cell from top to bottom by clicking on it and pressing **Shift+Enter**:

1. **Cell 1** installs FFmpeg, yt-dlp, and faster-whisper. Wait for it to finish.
2. **Cell 2** loads the project's Python code. It should print "Project loaded from: ..." if successful.
3. **Cell 3** asks for your YouTube URL. Type or paste it and press Enter.
4. **Cell 4** sets up the working directory. This is quick.
5. **Cell 5** downloads the source video. This can take several minutes.
6. **Cell 6** transcribes the audio. The Whisper model downloads on first use (~75 MB), then transcribes locally. This can take 5-15 minutes.
7. **Cell 7** selects three clip intervals. This is fast.
8. **Cell 8** renders the three clips with FFmpeg. This can take 5-20 minutes depending on video length.
9. **Cell 9** validates the clips with ffprobe. This is fast.
10. **Cell 10** previews the clips inline.
11. **Cell 11** downloads each clip to your computer.
12. **Cell 12** downloads all clips as a single ZIP file.
13. **Cell 13** (optional) copies clips to your Google Drive if you authorize it.

### Step 6: Download your clips

**Important**: Download your clips using Cells 11 or 12 before closing the browser tab. Colab temporary files are deleted when the session ends.

## Troubleshooting

### "Project code not found" in Cell 2

The notebook cannot find the `backend/app/` directory. Make sure you:
- Extracted the ZIP file (right-click in the file browser, choose Extract)
- The extracted folder has a `backend/` subfolder containing `app/`

If the folder has a different name, you can set it manually by adding a cell before Cell 2 with:
```python
import pathlib
PROJECT_DIR = pathlib.Path("/content/your-folder-name")
```

### Download failed

- Make sure the YouTube URL is valid and the video is public or unlisted
- Some videos restrict downloads (age-restricted, region-locked, or DRM-protected)
- Try a different video

### Transcription failed

- The video may have no speech. Captions require spoken audio
- The Whisper model download may have failed. Rerun Cell 1 and Cell 6
- If you run out of RAM, try a shorter video

### Rendering failed

- FFmpeg may have run out of memory. Try a shorter or lower-resolution source video
- Check that Cell 1 completed successfully (FFmpeg installed)

### Session disconnected

Colab free sessions disconnect after about 90 minutes of inactivity or after ~12 hours of runtime. If this happens:
- Reconnect by clicking **Reconnect** in the Colab menu
- You will likely need to rerun all cells from the top
- Any files not downloaded to your computer or Google Drive are lost

### "Your browser does not support the video tag"

This means the preview in Cell 10 cannot display. The clips are still valid — use the download cells (11 or 12) to get them.

## What this costs

**Nothing.** This workflow uses:
- Google Colab free tier (CPU runtime)
- FFmpeg (free, open-source, pre-installed on Colab)
- yt-dlp (free, open-source)
- faster-whisper with the "tiny" model (free, runs locally on CPU, no API key)

No payment card, no paid APIs, no subscription.

## What this does NOT require

- A local Python installation
- A payment card or credit card
- API keys of any kind
- A permanently running server
- Your computer to stay on (Colab runs in the cloud)
- Ollama or any LLM service
