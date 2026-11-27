# J.A.R.V.I.S Mobile Pro (Android PWA + APK + PC Bridge)

3 ta rejim bitta loyihada:

1. **Mustaqil Mobil PWA (`pwa/`)** — Android Chrome'da ochib *"Bosh ekranga qo'shish"* (Add to Home screen) qilsangiz, alohida ilova bo'lib o'rnatiladi. Gemini API kalitini ⚙ Sozlama bo'limiga kiritganingizdan so'ng kompyuter o'chiq paytda ham telefonda mustaqil o'zbekcha ovozli AI + kamera tahlili ishlaydi.
2. **Haqiqiy Android APK (`android-apk/`)** — Kotlin WebView + Native Android TextToSpeech (`uz-UZ`) + Mikrofon/Kamera ruxsatlari bilan tayyor Gradle loyiha. Android Studio'da ochib `Build APK` bosing yoki GitHub'ga yuklasangiz `.github/workflows/build-apk.yml` avtomatik `JARVIS-Mobile-APK` ni yig'ib beradi.
3. **Uy Kompyuteriga Ulanish (`bridge_server.py` + `start_internet_tunnel.bat`)** — Uy Wi-Fi (`:8765`) yoki Cloudflare HTTPS Tunnel orqali dunyoning istalgan joyidan kompyuteringizni boshqaradi va tayyor havolani `@jarvistdiubot` Telegramingizga yuboradi.
