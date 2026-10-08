
import asyncio
from playwright.async_api import async_playwright
import os

async def yandex_lens_screenshot(image_path: str, output_path: str) -> bool:
    """
    Uploads an image to Yandex Images and captures a screenshot of the results.
    Uses Headful mode to bypass basic anti-bot interactions.
    """
    print(f"🕵️‍♂️ [YandexLens] Starting logic for {image_path}")
    if not os.path.exists(image_path):
        print("❌ Image file not found.")
        return False

    async with async_playwright() as p:
        try:
            # STEALTH ARGS (Same as Google)
            args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled', 
                '--disable-infobars',
                '--window-size=1920,1080',
                '--start-maximized'
            ]
            
            # HEADFUL (Visible) to reduce Ban Risk
            print("🕵️‍♂️ [Yandex] Launching Browser...")
            browser = await p.chromium.launch(headless=False, args=args)
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                locale='en-US' # Yandex.com is English
            )
            
            page = await context.new_page()
            
            # 1. Go to Yandex Images
            await page.goto("https://yandex.com/images/", timeout=20000)
            await asyncio.sleep(1)
            
            # 2. Click Camera Icon (Search by image)
            # Yandex: usually has a class like 'cbir-icon' or 'icon_type_cbir' or button with name="cbir"
            print("🕵️‍♂️ [Yandex] Clicking Camera...")
            try:
                # Specify exact selectors seen in Yandex
                # '.cbir-icon' is common. Also 'button[aria-label="Search by image"]'
                await page.click('.cbir-icon, button[aria-label="Image search"]', timeout=5000)
            except:
                print("⚠️ [Yandex] Camera icon not found via simple selector. Trying robust search...")
                # Fallback
                await page.click('div.input__cbir-button button') 

            await asyncio.sleep(0.5)

            # 3. Upload File
            print("🕵️‍♂️ [Yandex] Uploading image...")
            input_selector = 'input[type="file"]'
            
            # Yandex input is usually explicitly named 'upfile'
            try:
                await page.wait_for_selector(input_selector, state='attached', timeout=5000)
                await page.set_input_files(input_selector, image_path)
            except Exception as e:
                print(f"❌ [Yandex] Input not found: {e}")
                await browser.close()
                return False
                
            # 4. Wait for Results
            print("🕵️‍♂️ [Yandex] Waiting for results (up to 40s)...")
            
            # Yandex can be slow. Wait for either URL change or a result element.
            # .CbirItem is a common class for results in Yandex Images
            # .cbir-section is the main container
            try:
                # Wait for URL or Element
                await page.wait_for_url("**/search?**", timeout=40000)
                await page.wait_for_selector('.cbir-section, .CbirItem, .cbir-panel', timeout=40000)
            except Exception as e:
                print(f"⚠️ [Yandex] Wait timeout, but checking content... {e}")
            
            await asyncio.sleep(2) # Stabilize
            
            # Check for Captcha (SmartCaptcha)
            content = await page.content()
            if "captcha" in content.lower() or "smartcaptcha" in content.lower():
                print("❌ [Yandex] Captcha Detected!")
                await page.screenshot(path=output_path) 
                await browser.close()
                return True # Return captcha shot
            
            # 5. Screenshot
            # Maybe remove search bar to see more results? 
            # Yandex layout is pretty good by default.
            await page.screenshot(path=output_path, full_page=False)
            
            print(f"✅ [Yandex] Screenshot saved to {output_path}")
            await browser.close()
            return True

        except Exception as e:
            print(f"❌ [Yandex] Playwright Error: {e}")
            try: await browser.close()
            except: pass
            return False
