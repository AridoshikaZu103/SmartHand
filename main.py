import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import drawing_utils
import numpy as np
import pyautogui
import psutil
import GPUtil
import time
import os
import ctypes
import sys
import threading

# Set Windows AppUserModelID so the taskbar icon displays properly instead of the default python icon
if sys.platform == "win32":
    myappid = 'smarthand.ai.controller.1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

# Disable pyautogui's pause and failsafe for responsive control
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# Path to the hand landmarker model and icon (handles PyInstaller temp directory)
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    
MODEL_PATH = os.path.join(application_path, "hand_landmarker.task")
ICON_PATH = os.path.join(application_path, "icon.ico")

# Hand landmark indices for fingertips
FINGER_TIP_INDICES = [4, 8, 12, 16, 20]

def set_window_icon(window_name):
    """Forces Windows to apply the custom icon.ico to the OpenCV window."""
    if sys.platform == "win32":
        hwnd = ctypes.windll.user32.FindWindowW(None, window_name)
        if hwnd:
            hicon = ctypes.windll.user32.LoadImageW(0, ICON_PATH, 1, 0, 0, 0x0010)
            if hicon:
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon) # ICON_SMALL
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon) # ICON_BIG

# ─────────────────────────────────────────────────────────────
# GESTURE MAP
#
# RIGHT HAND:
#   All fingers open              -> NEUTRAL (no action)
#   All fingers closed (Fist)     -> NEUTRAL (no action)
#   Thumb + Index                 -> Right arrow
#   Thumb + Index + Pinky         -> Left arrow
#   Index only                    -> Space
#   Thumb + Index + Middle        -> 'm' key
#   Thumb only                    -> 'enter' key
#   Index + Middle                -> Up arrow
#   Index + Pinky                 -> Down arrow
#   Index + Middle + Ring         -> 'ctrl+f4' key
#   Pinky only                    -> 'ctrl+t' key
#   Middle only                   -> 'z' key
#   4 Fingers (no pinky)          -> 'ctrl+win+right' key
#   4 Fingers (no thumb)          -> 'ctrl+alt+w' key
#
# LEFT HAND:
#   All fingers open              -> NEUTRAL (no action)
#   All fingers closed (Fist)     -> NEUTRAL (no action)
#   Index + Middle                -> 'f' key
#   Thumb + Index                 -> 'shift+n' key
#   Thumb + Index + Pinky         -> 'shift+p' key
#   Index only                    -> 'F11' key
#   Thumb only                    -> 'win+d' key
#   Index + Middle + Ring         -> 'alt+f4' key
#   Index + Pinky                 -> 'ctrl+alt+tab' key
#   4 Fingers (no pinky)          -> 'ctrl+win+left' key
#   4 Fingers (no thumb)          -> 'ctrl+alt+c' key
#   Thumb + Index + Middle        -> 'ctrl+tab'
#   Pinky only                    -> Pause/Resume gestures
#   Middle only                   -> 'x' key
#
# TWO-HAND COMBOS:
#   Left Fist + Right Index                   -> 'win+1'
#   Left Fist + Right Index + Middle          -> 'win+2'
#   Left Fist + Right Index + Middle + Ring   -> 'win+3'
#   Left Fist + Right 4 Fingers               -> 'win+4'
#   Left Index + Right Index                  -> 'tab'
#   Left Index + Right Index + Middle         -> Triple 'tab'
#   Left (Index+Middle) + Right (Thumb+Index)         -> 'alt+right'
#   Left (Index+Middle) + Right (Thumb+Index+Pinky)   -> 'alt+left'
#   Left (Thumb+Middle) + Right (Thumb+Middle)        -> Shutdown sequence
#   Left (Thumb+Middle+Ring+Pinky) + Right (Thumb+Middle+Ring+Pinky) -> Lock 'win+l'
#
# GLOBAL:
#   'z' Key                       -> Camera On/Off
# ─────────────────────────────────────────────────────────────

# How many consecutive frames a gesture must be held to trigger (Lowered for ultra-fast response)
HOLD_FRAMES = 2
# Cooldown in seconds after a gesture fires before it can fire again
COOLDOWN_TIME = 1.0

# ─────────────────────────────────────────────────────────────
# Threaded Webcam Stream (FPS Lag & Memory Fix)
# ─────────────────────────────────────────────────────────────
class WebcamVideoStream:
    def __init__(self, src=0, width=640, height=480):
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.stream.set(cv2.CAP_PROP_FPS, 30)
        self.stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.stream.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        (self.grabbed, self.frame) = self.stream.read()
        self.stopped = False

    def start(self):
        # Run background daemon thread to constantly flush buffer and read latest frame
        threading.Thread(target=self.update, args=(), daemon=True).start()
        return self

    def update(self):
        while True:
            if self.stopped:
                return
            # Constantly read to prevent OpenCV buffering bloat and FPS drops
            (self.grabbed, self.frame) = self.stream.read()

    def read(self):
        return self.grabbed, self.frame

    def stop(self):
        self.stopped = True
        self.stream.release()

    def isOpened(self):
        return self.stream.isOpened()

class GestureController:
    """Hand gesture recognition using MediaPipe Tasks API."""

    def __init__(self, num_hands=2, min_detection_confidence=0.3, min_tracking_confidence=0.3):
        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=num_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            result_callback=self._result_callback
        )
        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self.hand_connections = vision.HandLandmarksConnections.HAND_CONNECTIONS
        self.latest_result = None
        self.detected_hands = []

    def _result_callback(self, result: vision.HandLandmarkerResult, output_image: mp.Image, timestamp_ms: int):
        self.latest_result = result

    def process_frame(self, frame, timestamp_ms, draw=True):
        """Detect hand landmarks in the frame async and optionally draw them from cached result."""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # Send image to background worker
        self.landmarker.detect_async(mp_image, timestamp_ms)

        self.detected_hands = []
        
        # Use latest cached result to draw and parse hands
        if self.latest_result and self.latest_result.hand_landmarks:
            h, w, _ = frame.shape
            for i, hand_landmarks in enumerate(self.latest_result.hand_landmarks):
                handedness = None
                if self.latest_result.handedness and len(self.latest_result.handedness) > i:
                    handedness = self.latest_result.handedness[i][0].category_name

                # --- FRONT/BACK FILTER ---
                # Only allow gestures and landmarks when the BACK of the hand is facing the camera.
                # We calculate the 2D cross product of the Wrist->Index and Wrist->Pinky vectors.
                wrist = hand_landmarks[0]
                index_mcp = hand_landmarks[5]
                pinky_mcp = hand_landmarks[17]
                
                v1_x = index_mcp.x - wrist.x
                v1_y = index_mcp.y - wrist.y
                v2_x = pinky_mcp.x - wrist.x
                v2_y = pinky_mcp.y - wrist.y
                
                cross_product = (v1_x * v2_y) - (v1_y * v2_x)
                
                is_back_of_hand = False
                if handedness == "Right" and cross_product > 0:
                    is_back_of_hand = True
                elif handedness == "Left" and cross_product < 0:
                    is_back_of_hand = True
                    
                if not is_back_of_hand:
                    continue  # Ignore the hand entirely! (No landmarks, no gestures)
                # -------------------------

                if draw:
                    # Draw custom X-RAY bones (cyan)
                    if self.hand_connections:
                        for connection in self.hand_connections:
                            start_idx = connection[0]
                            end_idx = connection[1]
                            if start_idx < len(hand_landmarks) and end_idx < len(hand_landmarks):
                                start_pt = (int(hand_landmarks[start_idx].x * w), int(hand_landmarks[start_idx].y * h))
                                end_pt = (int(hand_landmarks[end_idx].x * w), int(hand_landmarks[end_idx].y * h))
                                cv2.line(frame, start_pt, end_pt, (255, 255, 0), 2, cv2.LINE_AA) # Cyan bones

                coord_x_list = []
                coord_y_list = []
                landmark_list = []
                for idx, lm in enumerate(hand_landmarks):
                    px, py = int(lm.x * w), int(lm.y * h)
                    coord_x_list.append(px)
                    coord_y_list.append(py)
                    landmark_list.append([idx, px, py])
                    if draw:
                        # Draw glowing joints
                        cv2.circle(frame, (px, py), 6, (255, 200, 0), cv2.FILLED) # Outer glow
                        cv2.circle(frame, (px, py), 3, (255, 255, 255), cv2.FILLED) # Inner core

                if draw and coord_x_list:
                    x_min, x_max = min(coord_x_list), max(coord_x_list)
                    y_min, y_max = min(coord_y_list), max(coord_y_list)
                    # Medical HUD bounding box (cyan)
                    cv2.rectangle(frame, (x_min - 20, y_min - 20),
                                  (x_max + 20, y_max + 20), (255, 255, 0), 1)
                    # Add corner brackets for X-Ray tech look
                    cv2.line(frame, (x_min - 20, y_min - 20), (x_min - 10, y_min - 20), (255, 255, 0), 3)
                    cv2.line(frame, (x_min - 20, y_min - 20), (x_min - 20, y_min - 10), (255, 255, 0), 3)
                    cv2.line(frame, (x_max + 20, y_max + 20), (x_max + 10, y_max + 20), (255, 255, 0), 3)
                    cv2.line(frame, (x_max + 20, y_max + 20), (x_max + 20, y_max + 10), (255, 255, 0), 3)
                                  
                self.detected_hands.append({
                    "handedness": handedness,
                    "landmarks": landmark_list
                })

        return frame

    def get_all_fingers_raised(self):
        """Determine which fingers are raised for all detected hands."""
        hands_dict = {}
        right_index_pos = None
        
        for hand in self.detected_hands:
            handedness = hand["handedness"]
            lm_list = hand["landmarks"]
            
            if len(lm_list) < 21 or handedness not in ["Left", "Right"]:
                continue
                
            if handedness == "Right":
                right_index_pos = (lm_list[8][1], lm_list[8][2])

            fingers = []

            # Thumb: left hand tip is > ip (right side in image), right hand tip is < ip
            thumb_tip_x = lm_list[FINGER_TIP_INDICES[0]][1]
            thumb_ip_x = lm_list[FINGER_TIP_INDICES[0] - 1][1]
            
            if handedness == "Left":
                fingers.append(1 if thumb_tip_x > thumb_ip_x else 0)
            elif handedness == "Right":
                fingers.append(1 if thumb_tip_x < thumb_ip_x else 0)

            # Other 4 fingers: tip y < PIP y means finger is raised
            for i in range(1, 5):
                tip_y = lm_list[FINGER_TIP_INDICES[i]][2]
                pip_y = lm_list[FINGER_TIP_INDICES[i] - 2][2]
                fingers.append(1 if tip_y < pip_y else 0)

            hands_dict[handedness] = fingers

        return hands_dict, right_index_pos

    def close(self):
        self.landmarker.close()


def match_gesture(hands_dict):
    """Match a finger pattern to a gesture based on active hands.
    Returns (gesture_name, action_type, key) or None."""
    if not hands_dict:
        return None

    # Check for two-hand combo gestures first
    if "Left" in hands_dict and "Right" in hands_dict:
        left_f = hands_dict["Left"]
        right_f = hands_dict["Right"]
        
        # Left: Index only, Right: Index only -> single tab
        if left_f == [0, 1, 0, 0, 0] and right_f == [0, 1, 0, 0, 0]:
            return ("LEFT INDEX + RIGHT INDEX", "hotkey", ["tab"])
        # Left: Index only, Right: Index + Middle -> triple tab
        elif left_f == [0, 1, 0, 0, 0] and right_f == [0, 1, 1, 0, 0]:
            return ("LEFT INDEX + RIGHT 2 FINGERS", "key", ["tab", "tab", "tab"])
            
        # Left: All closed (Fist)
        elif all(f == 0 for f in left_f):
            # Right: Index only -> win+1
            if right_f == [0, 1, 0, 0, 0]:
                return ("LEFT FIST + RIGHT INDEX", "hotkey", ["win", "1"])
            # Right: Index + Middle -> win+2
            elif right_f == [0, 1, 1, 0, 0]:
                return ("LEFT FIST + RIGHT 2 FINGERS", "hotkey", ["win", "2"])
            # Right: Index + Middle + Ring -> win+3
            elif right_f == [0, 1, 1, 1, 0]:
                return ("LEFT FIST + RIGHT 3 FINGERS", "hotkey", ["win", "3"])
            # Right: 4 Fingers (no thumb) -> win+4
            elif right_f == [0, 1, 1, 1, 1]:
                return ("LEFT FIST + RIGHT 4 FINGERS", "hotkey", ["win", "4"])
            # Right: Index + Pinky -> win
            elif right_f == [0, 1, 0, 0, 1]:
                return ("LEFT FIST + RIGHT IDX+PNK", "hotkey", ["win"])
            # Right: Thumb + Index + Pinky -> win+r
            elif right_f == [1, 1, 0, 0, 1]:
                return ("LEFT FIST + RIGHT TH+IDX+PNK", "hotkey", ["win", "r"])

        # Left: Thumb + Index + Middle
        elif left_f == [1, 1, 1, 0, 0]:
            if right_f == [0, 1, 0, 0, 0]:
                return ("CTRL+SHIFT+1", "hotkey", ["ctrl", "shift", "1"])
            elif right_f == [0, 1, 1, 0, 0]:
                return ("CTRL+SHIFT+2", "hotkey", ["ctrl", "shift", "2"])
            elif right_f == [0, 1, 1, 1, 0]:
                return ("CTRL+SHIFT+3", "hotkey", ["ctrl", "shift", "3"])
            elif right_f == [0, 1, 1, 1, 1]:
                return ("CTRL+SHIFT+4", "hotkey", ["ctrl", "shift", "4"])
            elif right_f == [0, 1, 0, 0, 1]:
                return ("F1", "hotkey", ["f1"])
            elif right_f == [1, 0, 0, 0, 1]:
                return ("F1", "hotkey", ["f1"])
            elif right_f == [1, 1, 0, 0, 1]:
                return ("F1", "hotkey", ["f1"])

        # Left: Index + Middle + Ring [0, 1, 1, 1, 0]
        elif left_f == [0, 1, 1, 1, 0]:
            # Right: Index -> ctrl + c
            if right_f == [0, 1, 0, 0, 0]:
                return ("CTRL+C", "hotkey", ["ctrl", "c"])
            # Right: Thumb + Index + Pinky -> ctrl + win + f4
            elif right_f == [1, 1, 0, 0, 1]:
                return ("CTRL+WIN+F4", "hotkey", ["ctrl", "win", "f4"])
            # Right: Index + Pinky -> macro new desktop
            elif right_f == [0, 1, 0, 0, 1]:
                return ("MACRO NEW DESKTOP", "macro_new_desktop", None)
            # Right: Index + Middle -> ctrl + x
            elif right_f == [0, 1, 1, 0, 0]:
                return ("CTRL+X", "hotkey", ["ctrl", "x"])
            # Right: Index + Middle + Ring -> ctrl + v
            elif right_f == [0, 1, 1, 1, 0]:
                return ("CTRL+V", "hotkey", ["ctrl", "v"])
            # Right: Index + Middle + Ring + Pinky -> ctrl + s
            elif right_f == [0, 1, 1, 1, 1]:
                return ("CTRL+S", "hotkey", ["ctrl", "s"])
                
        # Left: Middle + Ring + Pinky [0, 0, 1, 1, 1]
        elif left_f == [0, 0, 1, 1, 1]:
            # Right: Index -> macro open cmd
            if right_f == [0, 1, 0, 0, 0]:
                return ("MACRO OPEN CMD", "macro_open_cmd", None)
            # Right: Index + Middle -> macro open powershell
            elif right_f == [0, 1, 1, 0, 0]:
                return ("MACRO OPEN POWERSHELL", "macro_open_powershell", None)
            # Right: Index + Middle + Ring -> macro clear boost display
            elif right_f == [0, 1, 1, 1, 0]:
                return ("CTRL+SHIFT+WIN+B", "hotkey", ["ctrl", "shift", "win", "b"])

        # Left: Index + Middle
        elif left_f == [0, 1, 1, 0, 0]:
            # Right: Thumb + Index
            if right_f == [1, 1, 0, 0, 0]:
                return ("ALT + RIGHT ARROW", "hotkey", ["alt", "right"])
            # Right: Thumb + Index + Pinky
            elif right_f == [1, 1, 0, 0, 1]:
                return ("ALT + LEFT ARROW", "hotkey", ["alt", "left"])
                
        # Left: Thumb + Middle
        elif left_f == [1, 0, 1, 0, 0]:
            # Right: Thumb + Middle -> Shutdown Sequence
            if right_f == [1, 0, 1, 0, 0]:
                return ("SHUTDOWN", "shutdown", None)
                
        # Left: Thumb + Middle + Ring + Pinky
        elif left_f == [1, 0, 1, 1, 1]:
            # Right: Thumb + Middle + Ring + Pinky -> Lock
            if right_f == [1, 0, 1, 1, 1]:
                return ("LOCK PC", "lock", None)
                
        # Left: Thumb + Pinky
        elif left_f == [1, 0, 0, 0, 1]:
            # Right: Thumb + Pinky -> Task Manager
            if right_f == [1, 0, 0, 0, 1]:
                return ("TASK MANAGER", "hotkey", ["ctrl", "shift", "esc"])
                
        # Left: Thumb + Middle + Pinky
        elif left_f == [1, 0, 1, 0, 1]:
            # Right: Thumb + Middle + Pinky -> Restart
            if right_f == [1, 0, 1, 0, 1]:
                return ("RESTART PC", "restart", None)

    # Fallback: Process single hand if no combo matched
    # (Prioritize right hand if both are on screen but no combo matches)
    handedness = "Right" if "Right" in hands_dict else "Left"
    fingers = hands_dict[handedness]

    thumb, index, middle, ring, pinky = fingers

    # All open -> Neutral (Both Hands)
    if all(f == 1 for f in fingers):
        return ("OPEN (neutral)", "neutral", None)

    # All closed -> Neutral (Both Hands)
    if all(f == 0 for f in fingers):
        return ("FIST (neutral)", "neutral", None)

    if handedness == "Right":
        # Thumb + Index only -> Right arrow
        if thumb == 1 and index == 1 and middle == 0 and ring == 0 and pinky == 0:
            return ("RIGHT ARROW", "key", "right")

        # Thumb + Index + Pinky -> Left arrow
        if thumb == 1 and index == 1 and middle == 0 and ring == 0 and pinky == 1:
            return ("LEFT ARROW", "key", "left")

        # Index only -> Space
        if thumb == 0 and index == 1 and middle == 0 and ring == 0 and pinky == 0:
            return ("SPACE", "key", "space")

        # Thumb + Index + Middle -> 'm'
        if thumb == 1 and index == 1 and middle == 1 and ring == 0 and pinky == 0:
            return ("KEY 'm'", "key", "m")

        # Thumb only -> enter
        if thumb == 1 and index == 0 and middle == 0 and ring == 0 and pinky == 0:
            return ("ENTER", "key", "enter")

        # Index + Middle -> arrow up
        if thumb == 0 and index == 1 and middle == 1 and ring == 0 and pinky == 0:
            return ("UP ARROW", "key", "up")

        # Index + Pinky -> arrow down
        if thumb == 0 and index == 1 and middle == 0 and ring == 0 and pinky == 1:
            return ("DOWN ARROW", "key", "down")

        # Pinky only -> ctrl+t
        if thumb == 0 and index == 0 and middle == 0 and ring == 0 and pinky == 1:
            return ("KEY 'ctrl+t'", "hotkey", ["ctrl", "t"])

        # Middle only -> z
        if thumb == 0 and index == 0 and middle == 1 and ring == 0 and pinky == 0:
            return ("KEY 'z'", "key", "z")

        # Index + Middle + Ring -> ctrl+f4
        if thumb == 0 and index == 1 and middle == 1 and ring == 1 and pinky == 0:
            return ("KEY 'ctrl+f4'", "hotkey", ["ctrl", "f4"])

        # 4 Fingers (no pinky) -> ctrl+win+right
        if thumb == 1 and index == 1 and middle == 1 and ring == 1 and pinky == 0:
            return ("KEY 'ctrl+win+right'", "hotkey", ["ctrl", "win", "right"])

        # 4 Fingers (no thumb) -> ctrl+alt+w
        if thumb == 0 and index == 1 and middle == 1 and ring == 1 and pinky == 1:
            return ("KEY 'ctrl+alt+w'", "hotkey", ["ctrl", "alt", "w"])
            
        # Thumb + Middle + Ring + Pinky -> esc
        if thumb == 1 and index == 0 and middle == 1 and ring == 1 and pinky == 1:
            return ("ESCAPE", "key", "esc")
            
        # Thumb + Pinky -> f5 (Refresh)
        if thumb == 1 and index == 0 and middle == 0 and ring == 0 and pinky == 1:
            return ("REFRESH", "key", "f5")
            
        # Thumb + Middle + Pinky -> mouse right click
        if thumb == 1 and index == 0 and middle == 1 and ring == 0 and pinky == 1:
            return ("RIGHT CLICK", "mouse_right_click", None)

    elif handedness == "Left":
        # Index + Middle -> 'f' key
        if thumb == 0 and index == 1 and middle == 1 and ring == 0 and pinky == 0:
            return ("KEY 'f'", "key", "f")

        # Thumb + Index only -> Shift + N
        if thumb == 1 and index == 1 and middle == 0 and ring == 0 and pinky == 0:
            return ("KEY 'shift+n'", "hotkey", ["shift", "n"])

        # Thumb + Index + Pinky -> Shift + P
        if thumb == 1 and index == 1 and middle == 0 and ring == 0 and pinky == 1:
            return ("KEY 'shift+p'", "hotkey", ["shift", "p"])

        # Index only -> F11
        if thumb == 0 and index == 1 and middle == 0 and ring == 0 and pinky == 0:
            return ("KEY 'F11'", "key", "f11")

        # Thumb only -> win+d
        if thumb == 1 and index == 0 and middle == 0 and ring == 0 and pinky == 0:
            return ("KEY 'win+d'", "hotkey", ["win", "d"])

        # Index + Middle + Ring -> alt+f4
        if thumb == 0 and index == 1 and middle == 1 and ring == 1 and pinky == 0:
            return ("KEY 'alt+f4'", "hotkey", ["alt", "f4"])

        # Index + Pinky -> ctrl+alt+tab
        if thumb == 0 and index == 1 and middle == 0 and ring == 0 and pinky == 1:
            return ("KEY 'ctrl+alt+tab'", "hotkey", ["ctrl", "alt", "tab"])

        # 4 Fingers (no pinky) -> ctrl+win+left
        if thumb == 1 and index == 1 and middle == 1 and ring == 1 and pinky == 0:
            return ("KEY 'ctrl+win+left'", "hotkey", ["ctrl", "win", "left"])

        # Thumb + Middle + Ring + Pinky -> ctrl+shift+t
        if thumb == 1 and index == 0 and middle == 1 and ring == 1 and pinky == 1:
            return ("KEY 'ctrl+shift+t'", "hotkey", ["ctrl", "shift", "t"])

        # 4 Fingers (no thumb) -> ctrl+alt+c
        if thumb == 0 and index == 1 and middle == 1 and ring == 1 and pinky == 1:
            return ("KEY 'ctrl+alt+c'", "hotkey", ["ctrl", "alt", "c"])

        # Thumb + Index + Middle -> ctrl+tab
        if thumb == 1 and index == 1 and middle == 1 and ring == 0 and pinky == 0:
            return ("KEY 'ctrl+tab'", "hotkey", ["ctrl", "tab"])

        # Pinky only -> Pause/Resume gestures
        if thumb == 0 and index == 0 and middle == 0 and ring == 0 and pinky == 1:
            return ("PAUSE/RESUME GESTURES", "toggle_gestures", None)

        # Middle only -> x
        if thumb == 0 and index == 0 and middle == 1 and ring == 0 and pinky == 0:
            return ("KEY 'x'", "key", "x")
            
        # Thumb + Middle + Pinky -> mouse left click
        if thumb == 1 and index == 0 and middle == 1 and ring == 0 and pinky == 1:
            return ("LEFT CLICK", "mouse_left_click", None)
            
        # Thumb + Pinky -> ctrl+r
        if thumb == 1 and index == 0 and middle == 0 and ring == 0 and pinky == 1:
            return ("KEY 'ctrl+r'", "hotkey", ["ctrl", "r"])

    return None


def put_text_glow(img, text, pos, font, scale, color, glow_color, thickness):
    cv2.putText(img, text, pos, font, scale, glow_color, thickness + 4, cv2.LINE_AA)
    cv2.putText(img, text, pos, font, scale, color, thickness, cv2.LINE_AA)

def get_hardware_stats():
    # CPU
    cpu_util = psutil.cpu_percent()
    # MEM
    mem = psutil.virtual_memory()
    mem_used_mb = int(mem.used / (1024 * 1024))
    
    # GPU
    try:
        gpus = GPUtil.getGPUs()
        if gpus:
            gpu_name = f"GPU {gpus[0].id}"
            gpu_mem = f"{int(gpus[0].memoryUsed)} MB"
        else:
            gpu_name = "Intel UHD 620"
            gpu_mem = "128 MB"
    except Exception:
        gpu_name = "Intel UHD 620"
        gpu_mem = "128 MB"
            
    return cpu_util, mem_used_mb, gpu_name, gpu_mem

def draw_hud(img, gesture_name, hands_dict, fps, hold_progress, is_cooldown, gestures_active):
    """Draw the heads-up display with MSI Afterburner style OSD."""
    h, w, _ = img.shape


    # MSI AFTERBURNER OSD STYLE (Top Left)
    font_osd = cv2.FONT_HERSHEY_SIMPLEX
    scale_osd = 0.6
    thick_osd = 2
    
    cpu_util, mem_used_mb, gpu_name, gpu_mem = get_hardware_stats()
    
    # Line 1: GPU
    cv2.putText(img, "GPU", (15, 30), font_osd, scale_osd, (50, 200, 50), thick_osd, cv2.LINE_AA)
    cv2.putText(img, gpu_name, (90, 30), font_osd, scale_osd, (0, 150, 255), thick_osd, cv2.LINE_AA)
    cv2.putText(img, gpu_mem, (280, 30), font_osd, scale_osd, (0, 100, 200), thick_osd, cv2.LINE_AA)
    
    # Line 2: MEM
    cv2.putText(img, "MEM", (15, 60), font_osd, scale_osd, (0, 255, 0), thick_osd, cv2.LINE_AA)
    cv2.putText(img, f"{mem_used_mb}", (90, 60), font_osd, scale_osd, (0, 150, 255), thick_osd, cv2.LINE_AA)
    cv2.putText(img, "MB", (160, 55), font_osd, 0.4, (0, 100, 200), thick_osd, cv2.LINE_AA) # unit
    
    # Line 3: CPU
    cv2.putText(img, "CPU", (15, 90), font_osd, scale_osd, (255, 100, 0), thick_osd, cv2.LINE_AA)
    cv2.putText(img, f"{int(cpu_util)}", (90, 90), font_osd, scale_osd, (0, 150, 255), thick_osd, cv2.LINE_AA)
    cv2.putText(img, "%", (130, 85), font_osd, 0.4, (0, 100, 200), thick_osd, cv2.LINE_AA) # unit

    # Line 4: FPS
    cv2.putText(img, "FPS", (15, 120), font_osd, scale_osd, (150, 50, 200), thick_osd, cv2.LINE_AA)
    cv2.putText(img, f"{int(fps)}", (90, 120), font_osd, scale_osd, (0, 150, 255), thick_osd, cv2.LINE_AA)

    # Line 5: Status
    if gestures_active:
        put_text_glow(img, "SYS: ACTIVE", (15, 160), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), (0, 150, 0), 1)
    else:
        put_text_glow(img, "SYS: PAUSED", (15, 160), cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 0, 255), (0, 0, 100), 1)
        put_text_glow(img, "(Left Pinky to resume)", (15, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), (0,0,0), 1)

    # Top-Right: Gesture & Progress
    if gesture_name and gestures_active:
        g_text = gesture_name.upper()
        if is_cooldown:
            g_color = (150, 150, 150)
            g_glow = (50, 50, 50)
            g_text = "COOLDOWN"
        elif "neutral" in gesture_name.lower():
            g_color = (200, 200, 200)
            g_glow = (50, 50, 50)
        else:
            g_color = (255, 255, 255)  # Clean white text
            g_glow = (0, 150, 255)     # Cool amber glow for advanced look
            
        # Center the text appropriately on the right half, crisp and clean
        font_style = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.65
        thickness = 1
        
        text_size = cv2.getTextSize(g_text, font_style, font_scale, thickness)[0]
        text_x = w - text_size[0] - 30
        
        put_text_glow(img, g_text, (max(160, text_x), 45), font_style, font_scale, g_color, g_glow, thickness)

        # Draw Futuristic Progress Bar (sleek and thin, right-aligned under text)
        if hold_progress > 0 and not is_cooldown and "neutral" not in gesture_name.lower():
            bar_w = 150
            bar_x = w - bar_w - 30
            bar_y = 60
            bar_h = 4
            
            # Background track
            cv2.rectangle(img, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (50, 50, 50), -1)
            
            # Fill
            fill_w = int(bar_w * hold_progress)
            fill_color = (0, 255, 0) if hold_progress >= 1.0 else (0, 200, 255)
            cv2.rectangle(img, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), fill_color, -1)

    # 4. Bottom Bar: Hand & Finger Status
    if hands_dict:
        finger_names = ["TMB", "IDX", "MID", "RNG", "PNK"]
        
        for handedness, fingers in hands_dict.items():
            # Left hand goes on the left side, Right hand goes on the right side
            base_x = 20 if handedness == "Left" else w // 2 + 20
            
            hand_color = (255, 150, 50) if handedness == "Left" else (50, 150, 255)
            put_text_glow(img, f"{handedness.upper()}", (base_x, h - 25), cv2.FONT_HERSHEY_DUPLEX, 0.5, hand_color, (0, 0, 0), 1)
            
            for i, (name, f) in enumerate(zip(finger_names, fingers)):
                # Draw a small status indicator box
                box_x = base_x + 55 + (i * 35)
                box_y = h - 45
                
                # Active/Inactive background box
                bg_color = (0, 150, 0) if f else (30, 30, 30)
                cv2.rectangle(img, (box_x, box_y), (box_x + 30, box_y + 30), bg_color, -1)
                cv2.rectangle(img, (box_x, box_y), (box_x + 30, box_y + 30), (100, 100, 100), 1)
                
                # Finger initial (T, I, M, R, P)
                text_color = (255, 255, 255) if f else (100, 100, 100)
                cv2.putText(img, name[0], (box_x + 8, box_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, text_color, 1, cv2.LINE_AA)


def main():
    w = 640
    h = 480

    # Initialize Threaded Video Stream
    cap = WebcamVideoStream(src=0, width=w, height=h).start()

    detector = GestureController()
    frame_count = 0

    print("\n=== SmartHand Gesture Controller ===")
    print(f"Hold gesture for {HOLD_FRAMES} frames to trigger.")
    print(f"Cooldown: {COOLDOWN_TIME}s between actions.")
    print(f"GLOBAL TOGGLE: Press 'z' on keyboard to turn Camera On/Off.\n")
    print(f"To QUIT: Press 'x' on keyboard while camera window is focused.\n")
    print("RIGHT HAND gestures:")
    print("  All open / All closed     -> NEUTRAL (no action)")
    print("  Thumb + Index             -> Right Arrow")
    print("  Thumb + Index + Pinky     -> Left Arrow")
    print("  Index only                -> Space")
    print("  Thumb + Index + Middle    -> 'm' Key")
    print("  Thumb only                -> 'enter' Key")
    print("  Index + Middle            -> Up Arrow")
    print("  Index + Pinky             -> Down Arrow")
    print("  Pinky only                -> 'ctrl+t' Key")
    print("  Index + Ring              -> 'ctrl+f4' Key")
    print("  4 Fingers (no pinky)      -> 'ctrl+win+right' Key")
    print("  4 Fingers (no thumb)      -> 'ctrl+alt+w' Key\n")
    print("COMBO gestures:")
    print("  Left Fist + Right Index   -> 'win+1' Key")
    print("  Left Fist + Right Index+Mid-> 'win+2' Key")
    print("  Left Fist + Right Index+Mid+Ring-> 'win+3' Key")
    print("  Left Fist + Right 4 Fingers-> 'win+4' Key")
    print("  Left Fist + Right Index+Pinky -> 'win' Key")
    print("  Left Fist + Right Thumb+Idx+Pnk -> 'win+r' Key")
    print("  Left Thumb+Idx+Mid + Right Idx -> 'ctrl+shift+1'")
    print("  Left Thumb+Idx+Mid + Right Idx+Mid -> 'ctrl+shift+2'")
    print("  Left Thumb+Idx+Mid + Right Idx+Mid+Ring -> 'ctrl+shift+3'")
    print("  Left Thumb+Idx+Mid + Right 4 Fingers -> 'ctrl+shift+4'")
    print("  Left Index + Right Index  -> 'tab' Key")
    print("  Left Index + Right Index+Mid-> 'Triple Tab' Keys")
    print("  Left Idx+Mid+Ring + Right Idx -> 'ctrl+c'")
    print("  Left Idx+Mid+Ring + Right Th+Idx+Pnk -> 'ctrl+win+f4'")
    print("  Left Idx+Mid+Ring + Right Idx+Pnk -> MACRO New Desktop")
    print("  Left Idx+Mid+Ring + Right Idx+Mid -> 'ctrl+x'")
    print("  Left Idx+Mid+Ring + Right Idx+Mid+Ring -> 'ctrl+v'")
    print("  Left Idx+Mid+Ring + Right 4 Fingers -> 'ctrl+s'")
    print("  Left Mid+Ring+Pnk + Right Idx -> MACRO Clear Temp")
    print("  Left Mid+Ring+Pnk + Right Idx+Mid -> MACRO Clear %Temp%")
    print("  Left Mid+Ring+Pnk + Right Idx+Mid+Ring -> MACRO Clear Boost Display\n")
    print("LEFT HAND gestures:")
    print("  All open                  -> NEUTRAL (no action)")
    print("  All closed (Fist)         -> 'f' Key")
    print("  Thumb + Index             -> 'shift+n' Key")
    print("  Thumb + Index + Pinky     -> 'shift+p' Key")
    print("  Index only                -> 'F11' Key")
    print("  Thumb only                -> 'win+d' Key")
    print("  Index + Ring              -> 'alt+f4' Key")
    print("  Index + Pinky             -> 'ctrl+alt+tab' Key")
    print("  4 Fingers (no pinky)      -> 'ctrl+win+left' Key")
    print("  4 Fingers (no thumb)      -> 'ctrl+alt+c' Key")
    print("  Thumb + Index + Middle    -> 'ctrl+tab' Key")
    print("  Pinky only                -> Pause/Resume gestures")
    print("  Press 'x' to quit (in OpenCV window)")
    print("=" * 35 + "\n")

    prev_time = 0
    fps = 0

    # Hold-to-trigger state
    current_gesture_name = None
    hold_count = 0
    last_action_time = 0

    # Start/Stop state
    camera_active = True
    gestures_active = True
    
    screen_w, screen_h = pyautogui.size()

    while True:
        if not camera_active:
            # Display a blank screen if camera is off
            img = np.zeros((h, w, 3), dtype=np.uint8)
            cv2.putText(img, "CAMERA OFF", (w//2 - 100, h//2 - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(img, "Press 'z' to turn on", (w//2 - 110, h//2 + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
            cv2.imshow("SmartHand", img)
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('x'):
                break
            elif key == ord('z'):
                camera_active = True
                print("  [TOGGLE] Camera turning ON (Please wait...)")
                
                # Show 'Waiting...' screen immediately before the blocking camera call
                wait_img = np.zeros((h, w, 3), dtype=np.uint8)
                cv2.putText(wait_img, "Waiting...", (w//2 - 80, h//2 - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                cv2.putText(wait_img, "(takes ~10 seconds)", (w//2 - 110, h//2 + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
                cv2.imshow("SmartHand AI Controller", wait_img)
                set_window_icon("SmartHand AI Controller")
                cv2.waitKey(100)  # Force the window to render the text
                
                cap = WebcamVideoStream(src=0, width=w, height=h).start()
                print("  [TOGGLE] Camera turned ON")
            continue

        success, img = cap.read()
        if not success:
            continue

        # Force resize to w x h to drastically speed up processing 
        # (in case the camera ignores cap.set and feeds 1080p HD)
        img = cv2.resize(img, (w, h))

        # Use precise system time for LIVE_STREAM to ensure perfect sync
        # The previous 'frame_count * (1000 / 30)' forced the tracker out of sync with actual camera FPS!
        timestamp_ms = int(time.perf_counter() * 1000)

        img = detector.process_frame(img, timestamp_ms)
        hands_dict, right_index_pos = detector.get_all_fingers_raised()
        
        gesture = match_gesture(hands_dict)
        
        # If paused, ignore everything EXCEPT the unpause gesture
        if not gestures_active and gesture and gesture[1] != "toggle_gestures":
            gesture = None
            
        gesture_name = gesture[0] if gesture else None
        
        # If neutral, we don't trigger actions, but we still display it
        if gesture and gesture[1] == "neutral":
            gesture = None


        now = time.time()
        is_cooldown = (now - last_action_time) < COOLDOWN_TIME

        # ── Hold-to-trigger logic ──
        actionable_name = gesture[0] if gesture else None
        if actionable_name is not None:
            if actionable_name == current_gesture_name:
                hold_count += 1
            else:
                current_gesture_name = actionable_name
                hold_count = 1
        else:
            current_gesture_name = None
            hold_count = 0

        hold_progress = min(hold_count / HOLD_FRAMES, 1.0)

        # Fire the action once hold threshold is reached
        if hold_count == HOLD_FRAMES and not is_cooldown and gesture:
            action_type = gesture[1]
            key = gesture[2]

            if action_type == "key":
                if isinstance(key, list):
                    pyautogui.press(key, interval=0.15)  # 0.15s delay between sequential presses
                else:
                    pyautogui.press(key)
                print(f"  [KEY] {gesture[0]}")
            elif action_type == "hotkey":
                pyautogui.hotkey(*key)
                print(f"  [HOTKEY] {gesture[0]}")
            elif action_type == "macro_new_desktop":
                pyautogui.hotkey('ctrl', 'd')
                time.sleep(0.2)
                for _ in range(5):
                    pyautogui.press('tab')
                    time.sleep(0.05)
                pyautogui.press('space')
                time.sleep(0.2)
                for _ in range(2):
                    pyautogui.press('tab')
                    time.sleep(0.05)
                pyautogui.press('enter')
                time.sleep(0.2)
                pyautogui.press('left')
                time.sleep(0.2)
                pyautogui.press('enter')
                print("  [MACRO] New Desktop Sequence")
            elif action_type == "macro_open_cmd":
                pyautogui.hotkey('win', 'r')
                time.sleep(0.3)
                pyautogui.write('cmd')
                time.sleep(0.1)
                pyautogui.press('enter')
                print("  [MACRO] Open cmd")
            elif action_type == "macro_open_powershell":
                pyautogui.hotkey('win', 'r')
                time.sleep(0.3)
                pyautogui.write('powershell')
                time.sleep(0.1)
                pyautogui.press('enter')
                print("  [MACRO] Open powershell")
            elif action_type == "toggle_gestures":
                gestures_active = not gestures_active
                print(f"  [TOGGLE] Gestures Active: {gestures_active}")
                
                # Reset hold state
                current_gesture_name = None
                hold_count = 0
                if not gestures_active:
                    print("  Gestures are now PAUSED.")
            elif action_type == "lock":
                import ctypes
                ctypes.windll.user32.LockWorkStation()
                print("  [ACTION] PC Locked")
            elif action_type == "shutdown":
                import os
                os.system("shutdown /s /t 10")  # 10 second delay so user can abort with shutdown /a if accidental
                print("  [ACTION] PC Shutting Down in 10s...")
            elif action_type == "restart":
                import os
                os.system("shutdown /r /t 10")  # 10 second delay so user can abort with shutdown /a if accidental
                print("  [ACTION] PC Restarting in 10s...")
            elif action_type == "mouse_right_click":
                pyautogui.rightClick()
                print("  [ACTION] Mouse Right Click")
            elif action_type == "mouse_left_click":
                pyautogui.leftClick()
                print("  [ACTION] Mouse Left Click")

            last_action_time = now
            hold_count = HOLD_FRAMES + 1  # fire only once per hold

        # Calculate FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time) if prev_time != 0 else 0
        prev_time = curr_time

        # Draw HUD on the image for crisp UI text
        draw_hud(img, gesture_name, hands_dict,
                 fps, hold_progress, is_cooldown, gestures_active)

        cv2.imshow("SmartHand AI Controller", img)
        set_window_icon("SmartHand AI Controller")

        key = cv2.waitKey(1) & 0xFF
        if key == ord('x'):
            break
        elif key == ord('z'):
            camera_active = False
            cap.stop()
            print("  [TOGGLE] Camera turned OFF")
            # Reset gesture hold state when turning off
            current_gesture_name = None
            hold_count = 0

    if cap.isOpened():
        cap.stop()
    detector.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()