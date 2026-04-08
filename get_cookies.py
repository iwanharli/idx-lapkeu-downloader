import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
import json
import os

async def harvest_cookies():
    async with async_playwright() as p:
        print("🚀 Memulai Browser Penyamar (Stealth Mode)...")
        browser = await p.chromium.launch(headless=True)
        
        # User agent modern
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        
        context = await browser.new_context(user_agent=ua)
        page = await context.new_page()
        
        # Terapkan stealth agar tidak ketahuan bot
        await stealth_async(page)
        
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
