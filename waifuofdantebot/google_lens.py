
import asyncio
from playwright.async_api import async_playwright
import os

async def google_lens_screenshot(image_path: str, output_path: str) -> bool:
    """
    Uploads an image to Google Lens and captures a screenshot of the results.
    Includes STEALTH techniques to avoid Captcha.
    """
    print(f"🕵️‍♂️ [GoogleLens] Starting logic for {image_path}")
    if not os.path.exists(image_path):
        print("❌ Image file not found.")
        return False

    async with async_playwright() as p:
        try:
            # STEALTH ARGS
            args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled', # CRITICAL: Hides 'navigator.webdriver'
                '--disable-infobars',
                '--window-size=1920,1080',
                '--start-maximized'
            ]
            
            # Launch Browser (Headful to avoid Captcha)
            # We use headless=False so Google sees a real GPU/Renderer context.
            print("🕵️‍♂️ Launching Visible Browser (To bypass Captcha)...")
            browser = await p.chromium.launch(headless=False, args=args)
            
            # Create Context with Real User Agent & Viewport
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='es-ES',
                timezone_id='America/Lima'
            )
            
            # Add init script to further hide webdriver property
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            page = await context.new_page()
            
            # 1. Provide a "referenced" navigation if possible or direct
            # Going to google.com first, then lens might look more natural
            print("🕵️‍♂️ Navigating to Google...")
            await page.goto("https://www.google.com/?hl=es", timeout=15000)
            await asyncio.sleep(1) # Human pause
            
            # 2. Go to Lens/Images
            print("🕵️‍♂️ Going to Image Search...")
            await page.goto("https://www.google.com/imghp?hl=es", timeout=15000)
            
            # Click Camera Icon
            print("🕵️‍♂️ Clicking Camera...")
            try:
                # Try multiple selectors
                btn = await page.wait_for_selector('div[aria-label="Buscar por imágenes"], div[aria-label="Search by image"], span.GKz10d, .nDcEnd', timeout=4000)
                await btn.click()
            except Exception as e: 
                print(f"⚠️ Camera icon not found: {e}")
                # Try direct upload URL if click fails? No, Google requires interaction usually.
                await browser.close()
                return False

            await asyncio.sleep(0.5)

            # 3. Upload File
            print("🕵️‍♂️ Uploading image...")
            input_selector = 'input[type="file"]'
            # Be robust waiting for input
            try:
                await page.wait_for_selector(input_selector, state='attached', timeout=3000)
                await page.set_input_files(input_selector, image_path)
            except:
                 # Initial click might have opened a drag modal
                 await page.set_input_files('input[name="encoded_image"]', image_path) # Fallback input name sometimes

            # 4. Wait for Results
            print("🕵️‍♂️ Waiting for results...")
            # If captcha appears, URL might stay on /search but with different content, or go to /sorry/
            try:
                await page.wait_for_url("**/search?**", timeout=20000)
            except:
                print("⚠️ URL did not change to search results. Captcha?")
            
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2) # Wait for images to render
            
            # CHECK FOR CAPTCHA
            title = await page.title()
            content = await page.content()
            
            if "sorry" in page.url or "captcha" in content.lower() or "unusual traffic" in content.lower():
                print("❌ Google Captcha Detected!")
                # Take screenshot of failure for debug?
                await page.screenshot(path=output_path) # Send the captcha to user so they see it
                await browser.close()
                return True # Return true so user sees the captcha image
            
            # 5. Take Screenshot
            # Remove cookie banner if present
            try:
                await page.evaluate("document.querySelectorAll('[aria-modal=\"true\"]').forEach(e => e.remove())")
            except: pass
            
            await page.screenshot(path=output_path, full_page=False)
            
            print(f"✅ Screenshot saved to {output_path}")
            await browser.close()
            return True

        except Exception as e:
            print(f"❌ Playwright Error: {e}")
            try: await browser.close()
            except: pass
            return False
