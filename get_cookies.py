import asyncio
from playwright.async_api import async_playwright
import json
import os

async def harvest_cookies():
    async with async_playwright() as p:
        print("🚀 Memulai Browser (Manual Stealth Mode)...")
        # Gunakan argumen agar tidak terlihat seperti otomasi
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        
        # User agent modern Windows
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        
        context = await browser.new_context(
            user_agent=ua,
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
            locale="id-ID",
            timezone_id="Asia/Jakarta"
        )
        
        page = await context.new_page()
        
        # Hapus tanda automation dari navigator
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("🔗 Menghubungkan ke IDX untuk memancing Cloudflare...")
        try:
            # Buka halaman utama dulu
            await page.goto("https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan", wait_until="networkidle", timeout=90000)
            
            print("⏳ Menunggu verifikasi Cloudstile (max 20 detik)...")
            # Kita tunggu sampai elemen "Laporan Keuangan" muncul, tandanya sudah lolos verifikasi
            success = False
            for _ in range(20):
                content = await page.content()
                if "Laporan Keuangan" in content:
                    success = True
                    break
                await asyncio.sleep(1)
            
            if success:
                print("✅ BERHASIL! Cloudflare terlewati.")
                # Ambil cookies
                cookies = await context.cookies()
                
                # Simpan ke file
                with open("cookies.json", "w") as f:
                    json.dump(cookies, f, indent=4)
                
                print(f"🍪 {len(cookies)} Cookies berhasil disimpan ke: cookies.json")
                
                # Test API dikit
                print("🧪 Mengetes API dengan cookie baru...")
                api_url = "https://www.idx.co.id/primary/Helper/GetEmiten?emitenType=s"
                response = await page.goto(api_url)
                if response.status == 200:
                    print("🎉 API TEST: SUKSES (200 OK)!")
                else:
                    print(f"❌ API TEST: GAGAL ({response.status})")
            else:
                print("❌ GAGAL melewati Cloudflare. Mungkin perlu jeda lebih lama atau IP sudah diblokir total.")
                # Simpan screenshot buat bukti gagalnya kenapa
                await page.screenshot(path="bypass_failed.png")
                print("📸 Screenshot kegagalan disimpan ke: bypass_failed.png")

        except Exception as e:
            print(f"⚠️ Terjadi Kesalahan: {e}")
        
        await browser.close()
        print("🏁 Selesai.")

if __name__ == "__main__":
    asyncio.run(harvest_cookies())
