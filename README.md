# ✋ SmartHand - Advanced AI Gesture Controller

Control your entire computer operating system using in-air, high-speed hand gestures! **SmartHand** uses a modern, state-of-the-art AI architecture capable of running at 60 FPS directly on standard laptop hardware.

## 🚀 Features

- **Advanced AI Vision:** Completely migrated to Google's state-of-the-art **MediaPipe Tasks API**, running in a high-performance asynchronous `LIVE_STREAM` mode.
- **Hardware Accelerated:** Uses DirectShow (`cv2.CAP_DSHOW`) and `MJPG` compression on a decoupled 640x480 hardware capture pipeline. This allows the AI models to process video blazingly fast without bogging down your CPU, guaranteeing 60 FPS performance!
- **Hardware Agnostic HUD:** A dynamic, futuristic UI overlay tracks your real-time FPS, CPU utilization, RAM usage, and GPU load (using `psutil` and `GPUtil`, with graceful fallbacks for integrated Intel laptop GPUs).
- **Hold-To-Trigger Logic:** Prevent accidental clicks! Gestures must be intentionally held for a set amount of frames before executing, backed by a visual progress bar and a global cooldown timer.
- **Multi-Hand Combo System:** You are no longer limited to one hand. Combine specific shapes on your Left Hand and Right Hand to unlock hidden hotkeys and exponential control combinations!
- **Global Toggles:** Instantly pause the entire camera system using the `'z'` key to save battery, or use your Left Pinky gesture to temporarily pause AI gesture tracking while keeping the camera live.

---

## 🧠 The "60" Coincidence

![MediaPipe Hand Landmarks](Images/hand-landmarks.png)

When both your hands are on the screen, the AI tracks **42 physical landmarks** (21 joints per hand) in 3D space. By using these 42 landmarks, this application currently supports exactly **60 unique hand gestures** (15 Right, 15 Left, and 30 Dual-Hand combos) to control your PC!

## 🖐️ Gesture Map

> **Note:** A "Neutral" state (all fingers open or all fingers completely closed into a fist) on your dominant hand performs no actions.

### 📸 Reference Postures

To ensure maximum tracking accuracy, please refer to the correct hand posture and dorsal angles below when using the application:

<p align="center">
  <img src="Images/CORRECT%20HAND%20POSTURE.png" alt="Correct Hand Posture" width="48%">
  <img src="Images/(dorsal%20side)%20of%20both%20hands.png" alt="Dorsal Side of Both Hands" width="46%">
</p>

### ➡️ Right Hand (Primary Controls)

| Gesture Shape                     | Action Triggered      |
| :-------------------------------- | :-------------------- |
| **Thumb + Index**                 | `Right Arrow`         |
| **Thumb + Index + Pinky**         | `Left Arrow`          |
| **Index Only**                    | `Space`               |
| **Middle Only**                   | `'z'` Key             |
| **Thumb + Index + Middle**        | `'m'` Key             |
| **Thumb Only**                    | `Enter`               |
| **Index + Middle**                | `Up Arrow`            |
| **Index + Pinky**                 | `Down Arrow`          |
| **Index + Middle + Ring**         | `Ctrl + F4`           |
| **Pinky Only**                    | `Ctrl + t`            |
| **4 Fingers (No Pinky)**          | `Ctrl + Win + Right`  |
| **4 Fingers (No Thumb)**          | `Ctrl + Alt + w`      |
| **Thumb + Middle + Ring + Pinky** | `Esc` Key             |
| **Thumb + Pinky**                 | `F5` Key (Refresh)    |
| **Thumb + Middle + Pinky**        | **Mouse Right-Click** |

### 🌐 Global Keyboard Overrides (Terminal/Window Focused)

| Key       | Action Triggered           |
| :-------- | :------------------------- |
| `'z'` Key | **Toggle Camera ON / OFF** |
| `'x'` Key | **Quit the Application**   |

### ⬅️ Left Hand (System Hotkeys)

| Gesture Shape                     | Action Triggered                      |
| :-------------------------------- | :------------------------------------ |
| **Index + Middle**                | `'f'` Key                             |
| **Thumb + Index**                 | `Shift + n`                           |
| **Thumb + Index + Pinky**         | `Shift + p`                           |
| **Index Only**                    | `F11` Key                             |
| **Middle Only**                   | `'x'` Key                             |
| **Thumb Only**                    | `Win + d` (Show Desktop)              |
| **Index + Middle + Ring**         | `Alt + F4` (Close Window)             |
| **Index + Pinky**                 | `Ctrl + Alt + Tab`                    |
| **4 Fingers (No Pinky)**          | `Ctrl + Win + Left`                   |
| **4 Fingers (No Thumb)**          | `Ctrl + Alt + c`                      |
| **Thumb + Middle + Pinky**        | **Mouse Left-Click**                  |
| **Thumb + Middle + Ring + Pinky** | `Ctrl + Shift + t`                    |
| **Thumb + Pinky**                 | `Ctrl + r`                            |
| **Thumb + Index + Middle**        | `Ctrl + Tab`                          |
| **Pinky Only**                    | **[TOGGLE] Pause/Resume AI Gestures** |

### 🤝 Multi-Hand Combos

| Left Hand                         | Right Hand                        | Action Triggered                    |
| :-------------------------------- | :-------------------------------- | :---------------------------------- |
| **Fist**                          | **Index**                         | `Win + 1`                           |
| **Fist**                          | **Index + Middle**                | `Win + 2`                           |
| **Fist**                          | **Index + Middle + Ring**         | `Win + 3`                           |
| **Fist**                          | **4 Fingers**                     | `Win + 4`                           |
| **Fist**                          | **Index + Pinky**                 | `Win`                               |
| **Fist**                          | **Thumb + Index + Pinky**         | `Win + r`                           |
| **Thumb + Index + Middle**        | **Index**                         | `Ctrl + Shift + 1`                  |
| **Thumb + Index + Middle**        | **Index + Middle**                | `Ctrl + Shift + 2`                  |
| **Thumb + Index + Middle**        | **Index + Middle + Ring**         | `Ctrl + Shift + 3`                  |
| **Thumb + Index + Middle**        | **4 Fingers (No Thumb)**          | `Ctrl + Shift + 4`                  |
| **Thumb + Index + Middle**        | **Index + Pinky**                 | `F1`                                |
| **Thumb + Index + Middle**        | **Thumb + Pinky**                 | `F1`                                |
| **Thumb + Index + Middle**        | **Thumb + Index + Pinky**         | `F1`                                |
| **Index**                         | **Index**                         | `Tab`                               |
| **Index**                         | **Index + Middle**                | `Tab` + `Tab` + `Tab` (Triple Tab)  |
| **Index + Middle**                | **Thumb + Index**                 | `Alt + Right Arrow`                 |
| **Index + Middle**                | **Thumb + Index + Pinky**         | `Alt + Left Arrow`                  |
| **Thumb + Middle**                | **Thumb + Middle**                | **[SHUTDOWN PC]**                   |
| **Thumb + Middle + Ring + Pinky** | **Thumb + Middle + Ring + Pinky** | **[LOCK PC]** `Win + l`             |
| **Thumb + Pinky**                 | **Thumb + Pinky**                 | `Ctrl + Shift + Esc` (Task Manager) |
| **Thumb + Middle + Pinky**        | **Thumb + Middle + Pinky**        | **[RESTART PC]**                    |
| **Index + Middle + Ring**         | **Index**                         | `Ctrl + c`                          |
| **Index + Middle + Ring**         | **Thumb + Index + Pinky**         | `Ctrl + Win + F4` (Close Desktop)   |
| **Index + Middle + Ring**         | **Index + Pinky**                 | **[MACRO] New Desktop Sequence**    |
| **Index + Middle + Ring**         | **Index + Middle**                | `Ctrl + x`                          |
| **Index + Middle + Ring**         | **Index + Middle + Ring**         | `Ctrl + v`                          |
| **Index + Middle + Ring**         | **4 Fingers (No Thumb)**          | `Ctrl + s`                          |
| **Middle + Ring + Pinky**         | **Index**                         | **[MACRO] Open CMD Sequence**       |
| **Middle + Ring + Pinky**         | **Index + Middle**                | **[MACRO] Open PowerShell Seq.**    |
| **Middle + Ring + Pinky**         | **Index + Middle + Ring**         | `Ctrl + Shift + Win + b`            |

---

## 📥 Quick Start (No Installation Required!)

The easiest way to use SmartHand on any Windows PC is to simply download the pre-built executable. You **do not** need to install Python or mess with the terminal!

1. Go to the **Releases** section on the right side of this GitHub repository page.
2. Download the latest `main.exe` file.
3. Right-click `main.exe` and select **"Run as administrator"** *(This is required for the hand gestures to control your keyboard globally!)*
> [!CAUTION]
> ⏳ **Please be patient!** The 3D AI models are very large, so it is completely normal for `main.exe` to take **10 to 20 seconds** to load and appear on your screen after clicking.

*(Note: Because this is a custom executable, Windows Defender might show a "Windows protected your PC" popup. Just click **More info** -> **Run anyway**).*

---

## 💻 Developer Setup (Running from Source)

If you are a developer or want to modify the code from scratch, follow these exact steps:

**Step 1: Download or Transfer the Files**
If downloading from GitHub, click the green **Code -> Download ZIP** button on the repository page and extract the folder. 
Alternatively, copy the entire `SmartHand` folder to the new computer via a USB drive or cloud storage.
*(Note: The `hand_landmarker.task` file is ~8MB and will be included automatically in the GitHub download. If sharing manually, you can safely delete the `dist` and `build` folders before sharing to save space, but you **MUST** include the `hand_landmarker.task` file as it contains the AI model!)*

**Step 2: Install Python**
1. Go to [python.org/downloads](https://www.python.org/downloads/) and download the latest version of Python for Windows (Python 3.14 or newer recommended).
2. Open the installer. **CRITICAL STEP:** Before clicking "Install Now", make sure to check the box at the bottom that says **"Add Python to PATH"**. If you forget this, the terminal commands won't work!
3. Click "Install Now" and wait for it to finish.
4. You can verify the installation by opening your terminal (or Command Prompt) and typing `python --version` to see the installed version.

**Step 3: Open the Terminal**
1. Open the `SmartHand` folder on the new computer.
2. Click on the address bar at the top of the file explorer, type `cmd`, and hit **Enter**. This will open a black terminal window directly inside that folder.

**Step 4: Install Dependencies**
In that black terminal window, copy and paste this command and hit Enter:
```bash
pip install -r requirements.txt
```
*This will download all the required AI models (MediaPipe, OpenCV) and control libraries (PyAutoGUI). It might take a minute or two.*

**Step 5: Run the App!**
Once the installation finishes, you can start the application by typing:
```bash
py main.py
```
*(If that says command not found, try typing `python main.py` or `py -3.xx main.py` instead, replacing `xx` with your version).*

That's it! The camera should light up and the AI gesture HUD will appear on the screen.

---

## 📦 Building an Executable

To build the application into a standalone Windows `.exe` that doesn't require Python installation, simply run the build script:
```powershell
.\rebuild.ps1
```
> [!CAUTION]
> ⏳ **Note:** This process bundles massive AI models and libraries into a single file. It is completely normal for this to take **4 to 5 minutes**. Do not close the terminal!

_The `hand_landmarker.task` AI model is automatically bundled directly into the executable by PyInstaller!_

---

## 📁 File Structure

This is the complete expected file structure for the SmartHand application:

```text
SmartHand/
├── main.py                 # The core AI hand gesture control application script
├── hand_landmarker.task    # The Google MediaPipe 3D AI model (CRITICAL to run)
├── requirements.txt        # Contains all required Python packages and AI libraries
├── run.ps1                 # Developer quick-start script to easily launch the app from source
├── rebuild.ps1             # PowerShell script to automatically compile main.py into a .exe
├── main.spec               # PyInstaller config that securely bundles the AI model into the .exe
└── README.md               # This documentation file
```
