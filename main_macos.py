import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import drawing_utils
import numpy as np
import psutil
import time
import os
import sys
import threading
from pynput.keyboard import Key, Controller


# macOS keyboard controller
keyboard = Controller()


# Path to the hand landmarker model (handles PyInstaller temp directory)
if getattr(sys, 'frozen', False):
   application_path = sys._MEIPASS
else:
   application_path = os.path.dirname(os.path.abspath(__file__))
  
MODEL_PATH = os.path.join(application_path, "hand_landmarker.task")


# Hand landmark indices for fingertips
FINGER_TIP_INDICES = [4, 8, 12, 16, 20]


# ─────────────────────────────────────────────────────────────
# GESTURE MAP - macOS VERSION
# Windows hotkeys converted to macOS equivalents
#
# LEFT HAND ONLY (Custom macOS Gestures):
#   t (Thumb only)                  -> return
#   ti (Thumb + Index)              -> right arrow
#   tim (Thumb + Index + Middle)    -> cmd + tab (app switcher)
#   timr (Thumb + Index + Middle + Ring) -> ctrl + tab (tab switcher)
#   tip (Thumb + Index + Pinky)     -> left arrow
#   i (Index only)                  -> space
#   im (Index + Middle)             -> up arrow
#   imr (Index + Middle + Ring)     -> ctrl + left arrow (prev space)
#   imrp (Index + Middle + Ring + Pinky) -> ctrl + right arrow (next space)
#   ip (Index + Pinky)              -> down arrow
#   pinky only                      -> Pause/Resume gestures
#
# GLOBAL:
#   'z' Key                         -> Camera On/Off
#   'x' Key                         -> Quit Application
# ─────────────────────────────────────────────────────────────


# How many consecutive frames a gesture must be held to trigger
HOLD_FRAMES = 2
# Cooldown in seconds after a gesture fires before it can fire again
COOLDOWN_TIME = 0.5


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


   def process_frame(self, frame, timestamp_ms, draw=True, skip_ai=False):
       """Detect hand landmarks in the frame async and optionally draw them from cached result."""
      
       if not skip_ai:
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
                   continue


               if draw:
                   # Draw custom X-RAY bones using MediaPipe drawing_utils
                   drawing_utils.draw_landmarks(
                       frame,
                       hand_landmarks,
                       self.hand_connections,
                       drawing_utils.DrawingSpec(color=(255, 200, 0), thickness=2, circle_radius=4),
                       drawing_utils.DrawingSpec(color=(255, 255, 0), thickness=2)
                   )


               coord_x_list = []
               coord_y_list = []
               landmark_list = []
               for idx, lm in enumerate(hand_landmarks):
                   px, py = int(lm.x * w), int(lm.y * h)
                   coord_x_list.append(px)
                   coord_y_list.append(py)
                   landmark_list.append([idx, px, py])


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
       left_index_pos = None
      
       for hand in self.detected_hands:
           handedness = hand["handedness"]
           lm_list = hand["landmarks"]
          
           if len(lm_list) < 21 or handedness not in ["Left", "Right"]:
               continue
              
           if handedness == "Left":
               left_index_pos = (lm_list[8][1], lm_list[8][2])


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


       return hands_dict, left_index_pos


   def close(self):
       self.landmarker.close()




def match_gesture(hands_dict):
   """Match a finger pattern to a gesture based on active hands.
   Returns (gesture_name, action_type, key) or None.
  
   macOS Version with ONLY LEFT HAND gestures.
   """
   if not hands_dict:
       return None


   # Process LEFT HAND ONLY
   if "Left" in hands_dict:
       left_f = hands_dict["Left"]
       thumb, index, middle, ring, pinky = left_f
      
       # LEFT HAND CUSTOM MACOS GESTURES
      
       # t (Thumb only) -> return
       if thumb == 1 and index == 0 and middle == 0 and ring == 0 and pinky == 0:
           return ("THUMB (return)", "key", "enter")
      
       # ti (Thumb + Index) -> right arrow
       if thumb == 1 and index == 1 and middle == 0 and ring == 0 and pinky == 0:
           return ("THUMB+INDEX (right arrow)", "key", "right")
      
       # tim (Thumb + Index + Middle) -> cmd + tab (app switcher)
       if thumb == 1 and index == 1 and middle == 1 and ring == 0 and pinky == 0:
           return ("THUMB+INDEX+MIDDLE (cmd+tab)", "hotkey", [Key.cmd, Key.tab])
      
       # timr (Thumb + Index + Middle + Ring) -> ctrl + tab (tab switcher)
       if thumb == 1 and index == 1 and middle == 1 and ring == 1 and pinky == 0:
           return ("THUMB+INDEX+MIDDLE+RING (ctrl+tab)", "hotkey", [Key.ctrl, Key.tab])
      
       # tip (Thumb + Index + Pinky) -> left arrow
       if thumb == 1 and index == 1 and middle == 0 and ring == 0 and pinky == 1:
           return ("THUMB+INDEX+PINKY (left arrow)", "key", "left")
      
       # i (Index only) -> space
       if thumb == 0 and index == 1 and middle == 0 and ring == 0 and pinky == 0:
           return ("INDEX (space)", "key", "space")
      
       # im (Index + Middle) -> up arrow
       if thumb == 0 and index == 1 and middle == 1 and ring == 0 and pinky == 0:
           return ("INDEX+MIDDLE (up arrow)", "key", "up")
      
       # imr (Index + Middle + Ring) -> ctrl + left arrow (prev space)
       if thumb == 0 and index == 1 and middle == 1 and ring == 1 and pinky == 0:
           return ("INDEX+MIDDLE+RING (ctrl+left)", "hotkey", [Key.ctrl, Key.left])
      
       # imrp (Index + Middle + Ring + Pinky) -> ctrl + right arrow (next space)
       if thumb == 0 and index == 1 and middle == 1 and ring == 1 and pinky == 1:
           return ("INDEX+MIDDLE+RING+PINKY (ctrl+right)", "hotkey", [Key.ctrl, Key.right])
      
       # ip (Index + Pinky) -> down arrow
       if thumb == 0 and index == 1 and middle == 0 and ring == 0 and pinky == 1:
           return ("INDEX+PINKY (down arrow)", "key", "down")
      
       # Pinky only -> Pause/Resume gestures
       if thumb == 0 and index == 0 and middle == 0 and ring == 0 and pinky == 1:
           return ("PINKY (pause/resume)", "toggle_gestures", None)
      
       # All open -> Neutral
       if all(f == 1 for f in left_f):
           return ("OPEN (neutral)", "neutral", None)
      
       # All closed (Fist) -> Neutral
       if all(f == 0 for f in left_f):
           return ("FIST (neutral)", "neutral", None)


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
  
   return cpu_util, mem_used_mb


def draw_hud(img, gesture_name, hands_dict, fps, hold_progress, is_cooldown, gestures_active):
   """Draw the heads-up display with MSI Afterburner style OSD."""
   h, w, _ = img.shape


   # MSI AFTERBURNER OSD STYLE (Top Left)
   font_osd = cv2.FONT_HERSHEY_SIMPLEX
   scale_osd = 0.6
   thick_osd = 2
  
   cpu_util, mem_used_mb = get_hardware_stats()
  
   # Line 1: MEM
   cv2.putText(img, "MEM", (15, 30), font_osd, scale_osd, (0, 255, 0), thick_osd, cv2.LINE_AA)
   cv2.putText(img, f"{mem_used_mb}", (90, 30), font_osd, scale_osd, (0, 150, 255), thick_osd, cv2.LINE_AA)
   cv2.putText(img, "MB", (160, 25), font_osd, 0.4, (0, 100, 200), thick_osd, cv2.LINE_AA)
  
   # Line 2: CPU
   cv2.putText(img, "CPU", (15, 60), font_osd, scale_osd, (255, 100, 0), thick_osd, cv2.LINE_AA)
   cv2.putText(img, f"{int(cpu_util)}", (90, 60), font_osd, scale_osd, (0, 150, 255), thick_osd, cv2.LINE_AA)
   cv2.putText(img, "%", (130, 55), font_osd, 0.4, (0, 100, 200), thick_osd, cv2.LINE_AA)


   # Line 3: FPS
   cv2.putText(img, "FPS", (15, 90), font_osd, scale_osd, (150, 50, 200), thick_osd, cv2.LINE_AA)
   cv2.putText(img, f"{int(fps)}", (90, 90), font_osd, scale_osd, (0, 150, 255), thick_osd, cv2.LINE_AA)


   # Line 4: Status
   if gestures_active:
       put_text_glow(img, "SYS: ACTIVE", (15, 120), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), (0, 150, 0), 1)
   else:
       put_text_glow(img, "SYS: PAUSED", (15, 120), cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 0, 255), (0, 0, 100), 1)
       put_text_glow(img, "(Pinky to resume)", (15, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), (0,0,0), 1)


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
           g_color = (255, 255, 255)
           g_glow = (0, 150, 255)
          
       font_style = cv2.FONT_HERSHEY_SIMPLEX
       font_scale = 0.65
       thickness = 1
      
       text_size = cv2.getTextSize(g_text, font_style, font_scale, thickness)[0]
       text_x = w - text_size[0] - 30
      
       put_text_glow(img, g_text, (max(160, text_x), 45), font_style, font_scale, g_color, g_glow, thickness)


       # Draw Futuristic Progress Bar
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


   # Bottom Bar: Hand & Finger Status
   if hands_dict:
       finger_names = ["TMB", "IDX", "MID", "RNG", "PNK"]
      
       for handedness, fingers in hands_dict.items():
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
              
               # Finger initial
               text_color = (255, 255, 255) if f else (100, 100, 100)
               cv2.putText(img, name[0], (box_x + 8, box_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, text_color, 1, cv2.LINE_AA)




def press_key_macos(key_name):
   """Press a single key using pynput (macOS compatible)."""
   try:
       if isinstance(key_name, Key):
           keyboard.press(key_name)
           keyboard.release(key_name)
       elif key_name == "enter":
           keyboard.press(Key.enter)
           keyboard.release(Key.enter)
       elif key_name == "space":
           keyboard.press(Key.space)
           keyboard.release(Key.space)
       elif key_name == "up":
           keyboard.press(Key.up)
           keyboard.release(Key.up)
       elif key_name == "down":
           keyboard.press(Key.down)
           keyboard.release(Key.down)
       elif key_name == "left":
           keyboard.press(Key.left)
           keyboard.release(Key.left)
       elif key_name == "right":
           keyboard.press(Key.right)
           keyboard.release(Key.right)
       else:
           keyboard.press(key_name)
           keyboard.release(key_name)
   except Exception as e:
       print(f"  [ERROR] Key press failed: {e}")




def hotkey_macos(keys):
   """Execute a hotkey combination using pynput (macOS compatible)."""
   try:
       # Press all keys
       for key_obj in keys:
           keyboard.press(key_obj)
      
       # Release all keys in reverse order
       for key_obj in reversed(keys):
           keyboard.release(key_obj)
   except Exception as e:
       print(f"  [ERROR] Hotkey failed: {e}")




def main():
   w = 640
   h = 480


   # Initialize Threaded Video Stream
   cap = WebcamVideoStream(src=0, width=w, height=h).start()


   detector = GestureController()
   frame_count = 0


   print("\n" + "="*50)
   print("=== SmartHand Gesture Controller - macOS ===")
   print("="*50)
   print(f"\nHold gesture for {HOLD_FRAMES} frames to trigger.")
   print(f"Cooldown: {COOLDOWN_TIME}s between actions.")
   print(f"GLOBAL TOGGLE: Press 'z' on keyboard to turn Camera On/Off.\n")
   print(f"To QUIT: Press 'x' on keyboard while camera window is focused.\n")
  
   print("LEFT HAND GESTURES - Custom macOS Mappings:")
   print("  ═" * 40)
   print("  t                    → Return")
   print("  ti                   → Right Arrow")
   print("  tim                  → Command + Tab (App Switcher)")
   print("  timr                 → Control + Tab (Tab Switcher)")
   print("  tip                  → Left Arrow")
   print("  i                    → Space")
   print("  im                   → Up Arrow")
   print("  imr                  → Control + Left Arrow (Prev Space)")
   print("  imrp                 → Control + Right Arrow (Next Space)")
   print("  ip                   → Down Arrow")
   print("  pinky                → Pause/Resume Gestures")
   print("  ═" * 40)
   print("="*50 + "\n")


   prev_time = 0
   fps = 0


   # Hold-to-trigger state
   current_gesture_name = None
   hold_count = 0
   last_action_time = 0


   # Start/Stop state
   camera_active = True
   gestures_active = True
  
   PROCESS_EVERY_Nth_FRAME = 4
   frame_count = 0
   hands_dict = {}
   gesture_name = None
   gesture = None


   while True:
       if not camera_active:
           # Display a blank screen if camera is off
           img = np.zeros((h, w, 3), dtype=np.uint8)
           cv2.putText(img, "CAMERA OFF", (w//2 - 100, h//2 - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
           cv2.putText(img, "Press 'z' to turn on", (w//2 - 110, h//2 + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
           cv2.imshow("SmartHand AI Controller - macOS", img)
           key = cv2.waitKey(1) & 0xFF
          
           if key == ord('x'):
               break
           elif key == ord('z'):
               camera_active = True
               print("  [TOGGLE] Camera turning ON (Please wait...)")
              
               # Show 'Waiting...' screen
               wait_img = np.zeros((h, w, 3), dtype=np.uint8)
               cv2.putText(wait_img, "Waiting...", (w//2 - 80, h//2 - 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
               cv2.putText(wait_img, "(takes ~10 seconds)", (w//2 - 110, h//2 + 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
               cv2.imshow("SmartHand AI Controller - macOS", wait_img)
               cv2.waitKey(100)
              
               cap = WebcamVideoStream(src=0, width=w, height=h).start()
               print("  [TOGGLE] Camera turned ON")
              
               # Grace period
               last_action_time = time.time() + 2.0
               current_gesture_name = None
               hold_count = 0
           continue


       success, img = cap.read()
       if not success:
           continue
          
       frame_count += 1
       skip_ai = (frame_count % PROCESS_EVERY_Nth_FRAME != 0)


       # Force resize to w x h
       img = cv2.resize(img, (w, h))


       # Use precise system time for LIVE_STREAM
       timestamp_ms = int(time.perf_counter() * 1000)


       img = detector.process_frame(img, timestamp_ms, skip_ai=skip_ai)
      
       if not skip_ai:
           hands_dict, left_index_pos = detector.get_all_fingers_raised()
          
           gesture = match_gesture(hands_dict)
          
           # If paused, ignore everything EXCEPT the unpause gesture
           if not gestures_active and gesture and gesture[1] != "toggle_gestures":
               gesture = None
              
           gesture_name = gesture[0] if gesture else None
          
           # If neutral, we don't trigger actions
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
                   for k in key:
                       press_key_macos(k)
                       time.sleep(0.1)
               else:
                   press_key_macos(key)
               print(f"  [KEY] {gesture[0]}")
           elif action_type == "hotkey":
               hotkey_macos(key)
               print(f"  [HOTKEY] {gesture[0]}")
           elif action_type == "toggle_gestures":
               gestures_active = not gestures_active
               print(f"  [TOGGLE] Gestures Active: {gestures_active}")
              
               # Reset hold state
               current_gesture_name = None
               hold_count = 0
               if not gestures_active:
                   print("  Gestures are now PAUSED.")


           last_action_time = now
           hold_count = HOLD_FRAMES + 1


       # Calculate FPS
       curr_time = time.time()
       fps = 1 / (curr_time - prev_time) if prev_time != 0 else 0
       prev_time = curr_time


       # Draw HUD
       draw_hud(img, gesture_name, hands_dict,
                fps, hold_progress, is_cooldown, gestures_active)


       cv2.imshow("SmartHand AI Controller - macOS", img)


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