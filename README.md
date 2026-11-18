# Sembako Nusa

## Database MySQL/MariaDB dan phpMyAdmin

1. Pastikan layanan MySQL atau MariaDB berjalan.
2. Buka phpMyAdmin (sering tersedia di `http://localhost/phpmyadmin`), pilih **Import**, lalu impor file `database.sql`. File ini membuat database `sembako_nusa` beserta tabel produk, pengaturan, pesanan, akun admin, dan rincian pesanan.
3. Pasang driver Python dari folder proyek:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Atur kredensial MySQL di PowerShell sesuai instalasi Anda:

   ```powershell
   $env:SEMBAKO_DB_HOST = "127.0.0.1"
   $env:SEMBAKO_DB_PORT = "3306"
   $env:SEMBAKO_DB_NAME = "sembako_nusa"
   $env:SEMBAKO_DB_USER = "root"
   $env:SEMBAKO_DB_PASSWORD = "isi-password-mysql-anda"
   ```

   Jika MySQL root tidak memakai kata sandi, kosongkan `SEMBAKO_DB_PASSWORD`.

5. Jalankan aplikasi:

   ```powershell
   python server.py
   ```

6. Buka `http://127.0.0.1:8000`. Saat situs pertama kali dibuka, aplikasi memigrasikan data lama bila tersedia atau membuat data produk awal.
7. Login admin ada di `http://127.0.0.1:8000/login.html`; dashboard hanya dapat dibuka setelah login di `http://127.0.0.1:8000/admin.html`. Login pertama adalah `admin` / `admin123`.

Jika database MySQL masih kosong dan `data\sembako.sqlite3` tersedia, server akan menyalin data SQLite lama satu kali ke MySQL. File SQLite lama tidak dihapus. Produk bawaan dan akun admin demo dibuat bila tabel MySQL masih kosong.

Foto produk disimpan pada kolom `products.photo` bertipe `MEDIUMTEXT`. Kata sandi admin disimpan sebagai hash PBKDF2. Akun demo belum menyediakan fitur ganti kata sandi; jangan buka server ini ke jaringan publik atau gunakan untuk data sensitif.

Server aplikasi hanya mendengarkan pada komputer lokal (`127.0.0.1`). Akses dari perangkat lain memerlukan konfigurasi hosting dan pengamanan tambahan.
