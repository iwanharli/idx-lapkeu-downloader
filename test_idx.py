import asyncio
from playwright.async_api import async_playwright
import time

async def check_idx():
    async with async_playwright() as p:
        print("🚀 Memulai Browser (Headless)...")
        browser = await p.chromium.launch(headless=True)
        
        # Gunakan User-Agent asli agar lebih meyakinkan
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        print("🔗 Menghubungkan ke IDX (Halaman Laporan Keuangan)...")
        try:
            # 1. Cek Halaman Web Utama
            await page.goto("https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan", timeout=60000)
            await asyncio.sleep(5) # Tunggu Cloudflare challenge jika ada
            
            title = await page.title()
            content = await page.content()
            
            print(f"📄 Judul Halaman: {title}")
            
            if "Cloudflare" in title or "Attention Required" in title or "blocked" in content.lower():
                print("❌ STATUS: TERBLOKIR oleh Cloudflare.")
            elif "Laporan Keuangan" in content:
                print("✅ STATUS: AKSES WEB SUKSES! Anda tidak diblokir di browser.")
            else:
                print("❓ STATUS: Tidak menentu. Perlu cek screenshot.")
            
            # Ambil screenshot buat bukti
            await page.screenshot(path="idx_check.png")
            print("📸 Screenshot disimpan ke: idx_check.png")

            # 2. Cek API Langsung
            print("\n🔗 Mengetes API GetEmiten Langsung...")
            api_url = "https://www.idx.co.id/primary/Helper/GetEmiten?emitenType=s"
            
            response = await page.goto(api_url)
            await asyncio.sleep(3)
            
            if response.status == 200:
                print("✅ STATUS API: SUKSES (200 OK)!")
                # print(await page.content())
            else:
                print(f"❌ STATUS API: GAGAL ({response.status})")

        except Exception as e:
            print(f"⚠️ Terjadi Kesalahan: {e}")
        
        await browser.close()
        print("\n🏁 Tes Selesai.")

if __name__ == "__main__":
    asyncio.run(check_idx())
