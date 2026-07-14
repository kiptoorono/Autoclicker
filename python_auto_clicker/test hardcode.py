import os
import time
import pyautogui
import sys

# Check for OpenCV
try:
    import cv2
except ImportError:
    print("[!] OpenCV not installed. Install: pip install opencv-python")
    sys.exit(1)

# ===== CONFIGURATION =====
SHARE_IMAGE = r"C:\Users\Rono\Desktop\Red-Car-master\Red-Car-master\python_auto_clicker\templates\share_btn_context.png"
COPY_IMAGE = r"C:\Users\Rono\Desktop\Red-Car-master\Red-Car-master\python_auto_clicker\templates\copy_btn_context.png"

# Region of Interest (ROI) – limit search to the right side of the screen
# Adjust these values based on your screen resolution and browser window.
# For a 1920x1080 screen, the Share button is usually in the bottom-right corner.
ROI = (1200, 200, 700, 800)  # (x, y, width, height) – tweak as needed

CONFIDENCE = 0.85            # higher = stricter matching
DELAY_AFTER_SHARE = 2.5      # seconds to wait for popup
DELAY_AFTER_COPY = 1.0
DELAY_AFTER_SCROLL = 1.5
MAX_RETRIES = 4
REPETITIONS = 20

# ===== FUNCTIONS =====

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def click_image(image_path, roi=None, confidence=CONFIDENCE, max_attempts=MAX_RETRIES):
    """
    Locate and click an image within an optional ROI.
    Returns True if clicked, False otherwise.
    """
    if not os.path.exists(image_path):
        log(f"[!] Image file missing: {image_path}")
        return False

    for attempt in range(1, max_attempts + 1):
        try:
            # Use ROI if provided
            location = pyautogui.locateOnScreen(
                image_path,
                confidence=confidence,
                grayscale=False,
                region=roi
            )
            if location:
                center = pyautogui.center(location)
                log(f"[*] Found at {center} (attempt {attempt})")
                pyautogui.moveTo(center.x, center.y, duration=0.1)
                pyautogui.click()
                return True
            else:
                log(f"[!] Not found (attempt {attempt}/{max_attempts})")
        except Exception as e:
            log(f"[!] Error: {type(e).__name__}: {e}")
        time.sleep(0.8)  # wait before retry

    log(f"[!] Giving up on {image_path}")
    return False


def main():
    log("=" * 70)
    log("TikTok Clicker (ROI + Context Templates)")
    log(f"Share template: {SHARE_IMAGE}")
    log(f"Copy template: {COPY_IMAGE}")
    log(f"ROI: {ROI}")
    log(f"Repetitions: {REPETITIONS}")
    log("=" * 70)
    log("Switch to TikTok in your browser now...")
    time.sleep(3)

    success = 0
    failed = 0

    for rep in range(1, REPETITIONS + 1):
        log(f"\n--- Repetition {rep}/{REPETITIONS} ---")

        # 1. Click Share
        if not click_image(SHARE_IMAGE, roi=ROI):
            log("[-] Share not found – skipping")
            failed += 1
            time.sleep(2)
            continue

        # 2. Wait for popup
        log(f"Waiting {DELAY_AFTER_SHARE}s for popup...")
        time.sleep(DELAY_AFTER_SHARE)

        # 3. Click Copy
        if click_image(COPY_IMAGE, roi=ROI):
            log("[✓] Copy clicked!")
            success += 1
            time.sleep(DELAY_AFTER_COPY)
            # 4. Scroll down only if copy succeeded
            log("↓ Scrolling to next video")
            pyautogui.press('down')
            time.sleep(DELAY_AFTER_SCROLL)
        else:
            log("[-] Copy not found – staying on this video")
            failed += 1
            # Optionally press Escape to close any leftover popup
            pyautogui.press('escape')
            time.sleep(1)

        # brief pause
        time.sleep(0.5)

    log("\n" + "=" * 70)
    log(f"✅ Done! Success: {success}, Failed: {failed}")
    log("=" * 70)


if __name__ == "__main__":
    main()