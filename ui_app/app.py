import streamlit as st
import asyncio
import os
import logging
import random
import pandas as pd
from playwright.async_api import async_playwright
import shutil
import re

# --- Configuration and Setup ---
st.set_page_config(page_title="Web Screenshotter", layout="wide")

SCREENSHOT_DIR = "screenshots"
ZIP_DIR = "zip_files"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(ZIP_DIR, exist_ok=True)

# User agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

# --- Core Asynchronous Screenshot Logic (Adapted from your script) ---

async def scroll_to_bottom(page, pause_time=1, max_scrolls=30):
    """Scrolls to the bottom of the page to load dynamic content."""
    last_height = await page.evaluate("() => document.body.scrollHeight")
    for _ in range(max_scrolls):
        await page.evaluate("() => window.scrollBy(0, document.body.scrollHeight)")
        await asyncio.sleep(pause_time)
        new_height = await page.evaluate("() => document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

async def take_screenshot(browser, url, index):
    """
    Navigates to a URL and takes a full-page screenshot.
    Returns a status message string.
    """
    context = None
    try:
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            java_script_enabled=True,
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True
        )
        page = await context.new_page()
        
        # Block heavy resources to speed up loading
        await page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,mp3,mp4,avi}", lambda route: route.abort())

        # Navigate to the page
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(2, 4))

        # Scroll to load everything
        await scroll_to_bottom(page)

        # Create a safe filename from the URL
        safe_name = re.sub(r'[:/\\?*&"<>|]', '_', url.split("//")[1])
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"{index+1}_{safe_name}.png")
        
        await page.screenshot(path=screenshot_path, full_page=True)
        return f"✅ Success: {url}"

    except Exception as e:
        error_message = str(e).splitlines()[0]
        return f"⚠️ Error on {url}: {error_message}"

    finally:
        if context:
            await context.close()

async def run_batch_processor(urls, progress_bar, log_container):
    """
    Processes a list of URLs concurrently and updates the UI in real-time.
    """
    st.session_state.logs = []
    log_container.info("🚀 Starting browser...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-sandbox'
            ]
        )
        
        tasks = [take_screenshot(browser, url, index) for index, url in enumerate(urls)]
        total_tasks = len(tasks)
        
        for i, future in enumerate(asyncio.as_completed(tasks)):
            result = await future
            st.session_state.logs.append(result)
            
            # Update logs in UI
            log_output = "\n".join(st.session_state.logs)
            log_container.markdown(f"```\n{log_output}\n```")

            # Update progress bar
            progress_bar.progress((i + 1) / total_tasks, text=f"Processed {i+1} of {total_tasks} URLs")

        await browser.close()
    
    log_container.success("🎉 All tasks completed!")
    st.session_state.processing_complete = True


# --- UI Helper Functions ---

def flush_files():
    """Deletes all screenshots and zip files."""
    for directory in [SCREENSHOT_DIR, ZIP_DIR]:
        if os.path.exists(directory):
            shutil.rmtree(directory)
        os.makedirs(directory)
    st.session_state.logs = []
    st.session_state.processing_complete = False
    st.session_state.zip_path = None
    st.toast("🧹 All screenshots and ZIP files have been flushed.", icon="🧹")


# --- Streamlit UI ---

st.title("📸 Web Screenshot Automation")
st.markdown("Upload a CSV file or paste URLs to automatically capture full-page screenshots.")

# Initialize session state
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'zip_path' not in st.session_state:
    st.session_state.zip_path = None

# --- Input Area ---
urls_to_process = []
input_tab1, input_tab2 = st.tabs(["📤 Upload CSV File", "📝 Paste URLs"])

with input_tab1:
    uploaded_file = st.file_uploader(
        "Choose a CSV file", 
        type="csv",
        help="The CSV should have a column named 'name' containing the domain names (e.g., google.com)."
    )
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            if 'name' in df.columns:
                urls_to_process = [f"https://{url}" for url in df['name'].dropna().unique()]
                st.success(f"Loaded {len(urls_to_process)} unique URLs from the CSV file.")
            else:
                st.error("CSV file must contain a column named 'name'.")
        except Exception as e:
            st.error(f"Error reading CSV file: {e}")

with input_tab2:
    url_input = st.text_area(
        "Enter up to 10 URLs (one per line)",
        height=250,
        placeholder="google.com\nstreamlit.io\ngithub.com"
    )
    if url_input:
        lines = [line.strip() for line in url_input.split('\n') if line.strip()]
        if len(lines) > 10:
            st.warning("You have entered more than 10 URLs. Only the first 10 will be processed.")
            lines = lines[:10]
        
        # Add https:// if missing
        urls_to_process = []
        for line in lines:
            if not line.startswith(('http://', 'https://')):
                urls_to_process.append(f"https://{line}")
            else:
                urls_to_process.append(line)

# --- Control Buttons and Process Execution ---
col1, col2 = st.columns([1, 4])

with col1:
    start_button = st.button("▶️ Start Processing", type="primary", use_container_width=True, disabled=not urls_to_process)

with col2:
    flush_button = st.button("🧹 Flush Screenshots", on_click=flush_files, use_container_width=True)

if start_button:
    flush_files() # Clear previous results before starting
    st.session_state.processing_complete = False
    
    # UI placeholders for real-time updates
    progress_bar = st.progress(0, text="Starting...")
    log_container = st.empty()
    
    with st.spinner("Processing... Please wait."):
        asyncio.run(run_batch_processor(urls_to_process, progress_bar, log_container))
    
    st.rerun() # Rerun the script to update the UI state after processing

# --- Output and Download Area ---
if st.session_state.processing_complete:
    st.header("Results", divider="blue")
    
    # Create ZIP file
    if not st.session_state.zip_path:
        if any(os.scandir(SCREENSHOT_DIR)):
            zip_filename = os.path.join(ZIP_DIR, "screenshots")
            shutil.make_archive(zip_filename, 'zip', SCREENSHOT_DIR)
            st.session_state.zip_path = f"{zip_filename}.zip"
        else:
             st.warning("Processing completed, but no screenshots were successfully generated.")


    if st.session_state.zip_path:
        with open(st.session_state.zip_path, "rb") as fp:
            st.download_button(
                label="📥 Download Screenshots (.zip)",
                data=fp,
                file_name="screenshots.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True
            )

    # Display final logs if they exist
    if st.session_state.logs:
        st.subheader("Final Log")
        final_log_output = "\n".join(st.session_state.logs)
        st.markdown(f"```\n{final_log_output}\n```")