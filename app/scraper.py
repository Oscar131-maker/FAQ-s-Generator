import sys
import time
import random
import trafilatura
from urllib.parse import urlparse
from lxml import html
import requests as std_requests
from curl_cffi import requests as cffi_requests


class UltimateScraper:
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        ]

    def _normalize_url(self, url):
        url = url.strip()
        parsed = urlparse(url)
        if not parsed.scheme:
            return f"https://{url}"
        return url

    def _is_valid_content(self, text):
        if not text or len(text) < 100:
            return False
            
        block_keywords = [
            "access denied", "security check", "please enable javascript", 
            "attention required", "cloudflare", "403 forbidden", "access to this page is forbidden"
        ]
        
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in block_keywords):
            return False
        return True

    def _extract_h1(self, html_content):
        try:
            tree = html.fromstring(html_content)
            h1 = tree.xpath('//h1//text()')
            if h1:
                return " ".join(h1).strip()
            return "Sin H1 detectado"
        except Exception:
            return "Error extrayendo H1"

    def _process_html(self, html_content, url, status_code=200):
        # Decode bytes if necessary
        if isinstance(html_content, bytes):
            html_content = html_content.decode('utf-8', errors='ignore')
            
        text = trafilatura.extract(html_content, include_comments=False)
        
        if not self._is_valid_content(text):
            return None
            
        h1_text = self._extract_h1(html_content)

        return {
            "url": url,
            "h1": h1_text,
            "full_text": text
        }

    def _level_1_standard(self, url):
        print("   🔹 Ejecutando Nivel 1 (Requests Estándar)...")
        try:
            headers = {'User-Agent': random.choice(self.user_agents)}
            response = std_requests.get(url, headers=headers, timeout=5, verify=False)
            
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            return self._process_html(response.text, url, response.status_code)
                
        except Exception as e:
            print(f"      ⚠️ Nivel 1 falló: {str(e)}")
            return None

    def _level_2_stealth(self, url):
        print("   🔸 Escalando a Nivel 2 (TLS Impersonation)...")
        try:
            response = cffi_requests.get(url, impersonate="chrome110", timeout=10)
            return self._process_html(response.text, url, response.status_code)
        except Exception as e:
            print(f"      ⚠️ Nivel 2 falló: {str(e)}")
            return None

    async def _level_3_nuclear(self, url):
        print("   ☢️ Escalando a Nivel 3 (Playwright Browser)...")
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=random.choice(self.user_agents),
                    viewport={'width': 1920, 'height': 1080}
                )
                await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                page = await context.new_page()
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2000)
                    content = await page.content()
                    
                    result = self._process_html(content, url)
                    
                    await browser.close()
                    return result
                except Exception as inner_e:
                    await browser.close()
                    raise inner_e
        except Exception as e:
            print(f"      ❌ Nivel 3 falló: {str(e)}")
            return None

    async def scrape(self, url):
        final_url = self._normalize_url(url)
        print(f"\n🚀 Iniciando extracción para: {final_url}")
        
        # Level 1 and 2 are sync, running them directly is "blocking" but fast enough or acceptable
        # If we wanted perfection we'd run them in executor, but let's keep it simple
        result = self._level_1_standard(final_url)
        if result: return result
        
        result = self._level_2_stealth(final_url)
        if result: return result
        
        result = await self._level_3_nuclear(final_url)
        if result: return result
        
        return None
