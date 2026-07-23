                               SCREEN TRANSLATOR OTOMATIS
==================================================================

CARA INSTALL (WAJIB DIBACA):
1. Install Python 3.9+ dari https://www.python.org/downloads/
   (saat install, centang "Add Python to PATH")

2. Install Tesseract OCR:
   - Download installer Windows di:
     https://github.com/UB-Mannheim/tesseract/wiki
   - PENTING: saat instalasi, di layar "Choose Components" pastikan
     centang paket bahasa yang Anda butuhkan (misalnya Indonesian,
     Japanese, Korean, Chinese) selain English -- defaultnya cuma
     English yang aktif.
   - Install di lokasi default (C:\\Program Files\\Tesseract-OCR)

3. Buka Command Prompt di folder ini, install library Python:
   pip install mss pytesseract pillow deep-translator

4. Jalankan:
   python screen_translator.py

