"""
Automated CardMarket page downloader using undetected-chromedriver.
This bypasses Cloudflare detection better than PyAutoGUI.

Usage:
    python selenium_downloader.py              # Download all pages

To test with limited pages, modify the main call:
    download_all_pages(max_pages=5)           # Download only 5 pages

Features:
    - Automatic session recovery if browser is closed/crashes
    - Skips already-downloaded pages (checks downloads/ folder)
    - Progress tracking with visual countdown between pages
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import InvalidSessionIdException, WebDriverException
import time
import random
import os
from tqdm import tqdm
from app.watcherbase import watcherbase
from app.config import PAGES_DIR, DOWNLOADS_DIR, IMAGES_DIR, get_setting


def create_browser():
    """
    Create a new undetected Chrome browser instance.
    Uses settings for headless mode and minimized state.

    Returns:
        WebDriver: Chrome driver instance, or None if creation failed
    """
    print("Initializing Chrome browser...")
    try:
        options = uc.ChromeOptions()

        # Check settings for headless mode
        if get_setting('browser_headless', False):
            options.add_argument('--headless')
            print("  Running in headless mode")

        # Check settings for minimized start
        browser_minimized = get_setting('browser_minimized', True)
        if browser_minimized and not get_setting('browser_headless', False):
            options.add_argument('--start-minimized')

        # Detect installed Chrome version to avoid chromedriver mismatch
        version_main = None
        try:
            import subprocess
            result = subprocess.run(
                ['reg', 'query', r'HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon', '/v', 'version'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if 'version' in line.lower():
                        ver = line.strip().split()[-1]
                        version_main = int(ver.split('.')[0])
                        print(f"  Detected Chrome version: {ver} (major: {version_main})")
                        break
        except Exception as e:
            print(f"  Could not detect Chrome version: {e}")

        if version_main:
            driver = uc.Chrome(options=options, version_main=version_main)
        else:
            driver = uc.Chrome(options=options)

        # Minimize the window programmatically (more reliable than --start-minimized)
        if browser_minimized and not get_setting('browser_headless', False):
            try:
                driver.minimize_window()
            except:
                pass  # Some environments don't support minimize
            print("[OK] Browser initialized (minimized)\n")
        else:
            print("[OK] Browser initialized\n")

        return driver

    except Exception as e:
        print(f"[ERROR] Failed to initialize browser: {e}")
        return None


def is_session_valid(driver):
    """
    Check if the browser session is still valid.

    Returns:
        bool: True if session is valid, False otherwise
    """
    if driver is None:
        return False
    try:
        # Try to access a simple property - this will fail if session is invalid
        _ = driver.current_url
        return True
    except (InvalidSessionIdException, WebDriverException):
        return False
    except Exception:
        return False


def get_already_downloaded():
    """
    Get list of page names that have already been downloaded in this session.
    Checks the downloads folder for .htm files.

    Returns:
        set: Set of page names (without .json extension) already downloaded
    """
    downloaded = set()
    try:
        for filename in os.listdir(DOWNLOADS_DIR):
            if filename.endswith(".htm"):
                # Extract page name from filename (format: counter_pagename.htm)
                parts = filename[:-4].split("_", 1)  # Remove .htm and split on first _
                if len(parts) > 1:
                    downloaded.add(parts[1])
    except Exception as e:
        print(f"[WARNING] Could not check downloads folder: {e}")
    return downloaded

def download_page_with_selenium(driver, page_name, counter):
    """
    Download a single CardMarket page using Selenium.

    Args:
        driver: Selenium WebDriver instance
        page_name: Name of the .json file (e.g., "Pokemon_Base-Set_Charizard.json")
        counter: Unique counter for naming the downloaded file

    Returns:
        str: "success", "failed", or "invalid_session" (needs browser restart)
    """
    try:
        page_link = watcherbase.get_address_from_name(page_name)
        print(f"\n{'='*60}")
        print(f"Downloading: {page_name}")
        print(f"URL: {page_link}")
        print(f"{'='*60}")

        # Navigate to the page
        driver.get(page_link)

        # Wait for initial page load (random delay to appear more human)
        initial_wait = random.uniform(3, 6)
        print(f"Waiting {initial_wait:.1f}s for page to load...")
        time.sleep(initial_wait)

        # Check for Cloudflare challenge
        print("Checking for Cloudflare challenge...")
        page_timeout = get_setting('page_load_timeout', 30)
        try:
            # Wait for Cloudflare to resolve
            WebDriverWait(driver, page_timeout).until(
                lambda d: "cardmarket.com" in d.current_url and "challenge" not in d.page_source.lower()
            )
            print("[OK] Cloudflare check passed or not present")
        except:
            print("[WARNING] Cloudflare challenge detected - waiting for manual resolution...")
            time.sleep(10)

        # Wait for the listings table to load
        print("Waiting for listings table...")
        try:
            WebDriverWait(driver, page_timeout // 2).until(
                EC.presence_of_element_located((By.CLASS_NAME, "table-body"))
            )
            print("[OK] Listings table loaded")
        except:
            print("[ERROR] Could not find listings table - page may have failed to load")
            return "failed"

        # Click "Show More" buttons to load all listings
        show_more_count = 0
        print("Looking for 'Show More' buttons...")
        while True:
            try:
                # Look for the "Show more articles" button
                # CardMarket uses various button formats, so we'll try multiple selectors
                show_more_button = None

                # Try to find button by text content
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for button in buttons:
                    if "show more" in button.text.lower() or "mehr artikel" in button.text.lower():
                        show_more_button = button
                        break

                if not show_more_button:
                    print(f"[OK] No more 'Show More' buttons found (clicked {show_more_count} times)")
                    break

                # Scroll the button into view
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", show_more_button)
                time.sleep(random.uniform(0.5, 1.5))

                # Click the button
                driver.execute_script("arguments[0].click();", show_more_button)
                show_more_count += 1
                print(f"  Clicked 'Show More' button ({show_more_count} times)")

                # Wait for new listings to load (random delay)
                time.sleep(random.uniform(2, 4))

                # Safety limit to prevent infinite loops
                show_more_limit = get_setting('show_more_limit', 20)
                if show_more_count >= show_more_limit:
                    print(f"[WARNING] Reached safety limit of {show_more_limit} 'Show More' clicks")
                    break

            except Exception as e:
                print(f"[OK] Finished clicking 'Show More' buttons (clicked {show_more_count} times)")
                break

        # Get the full page HTML
        print("Saving page HTML...")
        html_content = driver.page_source

        # Save to downloads folder with counter prefix
        filename = f"{counter}_{page_name[:-5]}.htm"
        if not os.path.isdir(DOWNLOADS_DIR):
            os.mkdir(DOWNLOADS_DIR)
        filepath = os.path.join(DOWNLOADS_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"[OK] Saved to: {filepath}")

        # Download product image if not already present (use driver to bypass Cloudflare)
        try:
            from bs4 import BeautifulSoup
            import base64
            parsed = BeautifulSoup(html_content, "lxml")
            canonical_name = watcherbase.get_name_from_address(parsed.find_all('link')[0]['href'])
            image_dest = os.path.join(IMAGES_DIR, canonical_name + ".jpg")
            if not os.path.exists(image_dest):
                card_slideshow = parsed.body.find('div', attrs={'class': 'card-slideshow'})
                if card_slideshow:
                    image_url = card_slideshow.find_all('div', attrs={'class': 'slide'})[1].find('img')['src']
                else:
                    image_url = parsed.body.find('section', attrs={'id': 'image'}).find('img')['src']
                image_b64 = driver.execute_async_script("""
                    var url = arguments[0], done = arguments[1];
                    fetch(url)
                        .then(r => r.arrayBuffer())
                        .then(buf => {
                            var bytes = new Uint8Array(buf), s = '';
                            for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
                            done(btoa(s));
                        })
                        .catch(() => done(null));
                """, image_url)
                if image_b64:
                    with open(image_dest, "wb") as f:
                        f.write(base64.b64decode(image_b64))
                    print(f"[OK] Downloaded image to: {image_dest}")
                else:
                    print(f"[WARNING] Image fetch returned null for {image_url}")
        except Exception as e:
            print(f"[WARNING] Could not download image: {e}")

        return "success"

    except InvalidSessionIdException as e:
        print(f"[ERROR] Browser session invalid - need to restart browser")
        return "invalid_session"

    except WebDriverException as e:
        if "invalid session id" in str(e).lower():
            print(f"[ERROR] Browser session invalid - need to restart browser")
            return "invalid_session"
        print(f"[ERROR] Error downloading {page_name}: {e}")
        return "failed"

    except Exception as e:
        print(f"[ERROR] Error downloading {page_name}: {e}")
        return "failed"


def download_all_pages(max_pages=None):
    """
    Download all pages from the pages/ directory using Selenium.
    Uses rate limiting to avoid Cloudflare detection.
    Automatically recovers from browser crashes/closures.
    Skips pages that have already been downloaded.

    Args:
        max_pages: Maximum number of pages to download (default: None = all pages)
    """
    print("\n" + "="*60)
    print("CardMarket Selenium Downloader")
    print("="*60)
    if max_pages:
        print(f"Max pages to download: {max_pages}")
    else:
        print(f"Downloading all pages")
    print(f"Delay between pages: 5-10 minutes (randomized)")
    print(f"Session recovery: Enabled (will restart browser if closed)")
    print("="*60 + "\n")

    # Get list of pages to download (only from pages/, not archive/)
    try:
        page_files = [f for f in os.listdir(PAGES_DIR) if f.endswith(".json")]
        if max_pages:
            page_files = page_files[:max_pages]  # Limit if specified

        if not page_files:
            print("[ERROR] No .json files found in pages/ directory")
            return

        # Check which pages have already been downloaded
        already_downloaded = get_already_downloaded()
        pages_to_download = []
        skipped = 0

        for page in page_files:
            page_name_no_ext = page[:-5]  # Remove .json
            if page_name_no_ext in already_downloaded:
                skipped += 1
            else:
                pages_to_download.append(page)

        if skipped > 0:
            print(f"[INFO] Skipping {skipped} already-downloaded page(s)")

        if not pages_to_download:
            print("[OK] All pages have already been downloaded!")
            return

        print(f"Found {len(pages_to_download)} page(s) to download:\n")
        for i, page in enumerate(pages_to_download, 1):
            print(f"  {i}. {page}")
        print()

    except Exception as e:
        print(f"[ERROR] Error reading pages directory: {e}")
        return

    # Initialize the browser
    driver = create_browser()
    if driver is None:
        return

    # Download each page
    successful = 0
    failed = 0
    counter = len(already_downloaded)  # Start counter from existing downloads

    try:
        i = 0
        while i < len(pages_to_download):
            page_name = pages_to_download[i]
            print(f"\n[Page {i+1}/{len(pages_to_download)}]")

            # Check if session is still valid before attempting download
            if not is_session_valid(driver):
                print("\n[WARNING] Browser session is invalid - attempting to restart...")
                try:
                    driver.quit()
                except:
                    pass
                driver = create_browser()
                if driver is None:
                    print("[ERROR] Could not restart browser - stopping download")
                    break
                print("[OK] Browser restarted successfully - continuing download\n")

            result = download_page_with_selenium(driver, page_name, counter)

            if result == "success":
                successful += 1
                counter += 1
                i += 1  # Move to next page
            elif result == "invalid_session":
                # Don't increment i - we'll retry this page after restarting browser
                print("\n[WARNING] Session invalidated - will restart browser and retry...")
                try:
                    driver.quit()
                except:
                    pass
                driver = create_browser()
                if driver is None:
                    print("[ERROR] Could not restart browser - stopping download")
                    break
                print("[OK] Browser restarted - retrying current page...\n")
                continue  # Retry same page
            else:  # "failed"
                failed += 1
                counter += 1
                i += 1  # Move to next page even on failure

            # Wait between downloads (except after the last one)
            if i < len(pages_to_download):
                wait_min = get_setting('download_wait_min', 5)
                wait_max = get_setting('download_wait_max', 10)
                wait_minutes = random.uniform(wait_min, wait_max)
                wait_seconds = int(wait_minutes * 60)
                print(f"\n[TIMER] Waiting {wait_minutes:.1f} minutes before next download...")
                print(f"   (This helps avoid Cloudflare detection)\n")

                # Visual countdown with tqdm progress bar
                with tqdm(total=wait_seconds, desc="   Countdown", unit="s",
                         bar_format='{desc}: {bar} {percentage:3.0f}% | {remaining}',
                         ncols=80) as pbar:
                    # Update every second, counting down
                    for elapsed in range(wait_seconds):
                        time.sleep(1)
                        pbar.update(1)

                        # Calculate remaining time for display
                        remaining = wait_seconds - elapsed - 1
                        mins = remaining // 60
                        secs = remaining % 60

                        # Update the postfix to show remaining time
                        if mins > 0:
                            pbar.set_postfix_str(f"{mins}m {secs}s remaining")
                        else:
                            pbar.set_postfix_str(f"{secs}s remaining")

                print()

    except KeyboardInterrupt:
        print("\n\n[WARNING] Download interrupted by user")

    finally:
        # Close the browser (safely - it might already be closed)
        print("\nClosing browser...")
        try:
            if driver is not None:
                driver.quit()
        except:
            pass

        # Print summary
        print("\n" + "="*60)
        print("DOWNLOAD SUMMARY")
        print("="*60)
        print(f"Skipped (already downloaded): {skipped}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Total attempted: {successful + failed}")
        print("="*60)

        # Import all downloaded pages to avoid slow first load in Flask app
        if successful > 0:
            print("\nProcessing downloaded pages...")
            try:
                watcherbase.import_all_pages()
                print("[OK] All pages imported successfully")
            except Exception as e:
                print(f"[ERROR] Failed to import pages: {e}")


if __name__ == "__main__":
    # Download all pages (or specify max_pages=5 for testing)
    download_all_pages()
