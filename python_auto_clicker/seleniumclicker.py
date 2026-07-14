import os
import time
import pyautogui
import sys
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.firefox import GeckoDriverManager

# ===== CONFIGURATION =====
COMMENT_IMAGE = r"C:\Users\Rono\Desktop\Red-Car-master\Red-Car-master\python_auto_clicker\templates\comment_btn.png"
RAW_LINKS_FILE = "raw_links_tiktok.txt"
CONFIDENCE = 0.80
MAX_ATTEMPTS = 3
REPETITIONS = 20

# ===== FIREFOX SETUP =====
def get_firefox_driver():
    options = FirefoxOptions()
    # Use your default profile (already logged in)
    profile_path = get_firefox_profile_dir()  # you'll need to import this from config
    if profile_path:
        options.add_argument(f"--profile={profile_path}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = FirefoxService(GeckoDriverManager().install())
    return webdriver.Firefox(service=service, options=options)

def get_firefox_profile_dir():
    # Quick fallback – define your own or import from config
    import os
    profiles_ini = os.path.join(os.environ.get('APPDATA', ''), r"Mozilla\Firefox\profiles.ini")
    if os.path.exists(profiles_ini):
        import configparser
        config = configparser.ConfigParser()
        config.read(profiles_ini)
        if config.has_section('Profile0'):
            path = config.get('Profile0', 'Path', fallback='')
            if path:
                return os.path.join(os.path.dirname(profiles_ini), path)
    return None

# ===== HELPERS =====
def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def click_image(image_path, confidence=CONFIDENCE, max_attempts=MAX_ATTEMPTS):
    for attempt in range(1, max_attempts + 1):
        try:
            location = pyautogui.locateOnScreen(image_path, confidence=confidence, grayscale=False)
            if location:
                center = pyautogui.center(location)
                log(f"[*] Found comment button at {center} (attempt {attempt})")
                pyautogui.moveTo(center.x, center.y, duration=0.1)
                pyautogui.click()
                return True
        except Exception as e:
            log(f"[!] Error: {e}")
        time.sleep(0.5)
    log(f"[!] Comment button not found after {max_attempts} attempts")
    return False

def save_raw_link(url):
    with open(RAW_LINKS_FILE, 'a') as f:
        f.write(url + "\n")

# ===== MAIN =====
def main():
    log("Starting Hybrid Comment Clicker...")
    driver = get_firefox_driver()
    driver.get("https://www.tiktok.com/foryou")
    time.sleep(5)

    collected = 0
    scroll_attempts = 0
    last_height = driver.execute_script("return document.body.scrollHeight")

    while collected < REPETITIONS:
        # Scroll down
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        # Find all video containers (or just scroll; we'll rely on image to find comment button)
        # We need to ensure the comment button is visible, so we scroll each video into view.
        video_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/video/')]")
        for link in video_links:
            if collected >= REPETITIONS:
                break
            try:
                # Scroll to the video
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link)
                time.sleep(1)

                # Click the comment button using image recognition
                if not click_image(COMMENT_IMAGE):
                    log("[-] Skipping – comment button not visible")
                    continue

                # Wait for overlay to open (address bar changes)
                time.sleep(2)
                # Read the URL
                current_url = driver.current_url
                # Clean it
                clean_url = current_url.split('?')[0].split('&')[0]
                if '/video/' in clean_url:
                    save_raw_link(clean_url)
                    log(f"[+] Captured: {clean_url}")
                    collected += 1
                else:
                    log("[-] URL doesn't contain video – skipping")

                # Close overlay (press Escape)
                driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                time.sleep(1)

            except Exception as e:
                log(f"[!] Error: {e}")
                continue

        # Check if scrolled to bottom
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            scroll_attempts += 1
            if scroll_attempts >= 3:
                log("[!] No more new content – stopping")
                break
        else:
            scroll_attempts = 0
            last_height = new_height

    driver.quit()
    log(f"✅ Done. Collected {collected} links.")

if __name__ == "__main__":
    main()