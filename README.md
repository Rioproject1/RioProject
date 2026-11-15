# RioProject
RioOS adalah dashboard management untuk server skala kecil dan sedang.. 
RioOS dapat di jalan kan di berbagai perangkat mulai dari STB Hingga komputer high end.

<img width="1334" height="642" alt="image" src="https://github.com/user-attachments/assets/bdba82ce-7131-4eaa-93c7-7e2d52133b86" />
<img width="1333" height="637" alt="image" src="https://github.com/user-attachments/assets/3b6a34f2-0c21-45a2-b959-9489f4c121b6" />

Spesifikasi minimum untuk Laptop,Stb,Dan Hp

CPU: 2 Core / 2 Thread (Intel Celeron, AMD E-Series, atau STB ARM Cortex-A53).

RAM: 1 GB - 2 GB (Ini udah cukup buat Python Flask + OS Linux ringan).

Penyimpanan: 8 GB - 16 GB (MicroSD / eMMC STB).

OS: Linux tanpa GUI (Armbian / Ubuntu Server) atau Termux di Android.

Spesifikasi yang di saran kan:

PU: 4 Core (Intel Core i3 gen 8+, AMD Ryzen 3, atau ARM Cortex-A73/A76).

RAM: 4 GB - 8 GB.

Penyimpanan: Wajib SSD/HDD (minimal 32 GB).

PENEMPATAN FOLDER/FILE IKUTIN TEKS BERIKUT AGAR TIDAK EROR 

RioOS/
├── app.py
├── requirements.txt
└── templates/
    ├── index.html
    └── login.html


Berikut cara menggunakan RioOS beserta dengan pkg nya 
MOHON BACA HINGGA AKHIR
# RioOS Dashboard Server Management

RioOS adalah aplikasi web untuk mengelola, memantau, dan menjalankan berbagai layanan server Linux melalui dashboard berbasis web.

## 1. Requirements / Bahan Instalasi

**Operating System:**

- Ubuntu / Debian Linux
- PC / Laptop (x86_64)
- STB / Perangkat Linux ARM64
- Koneksi internet

**System Packages:**

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv arp-scan iptables curl tar -y
```

**Python Dependencies:**

```bash
pip install -r requirements.txt
```

Dependencies utama:

- Flask
- psutil
- requests

## 2. Instalasi Ookla Speedtest CLI

RioOS menggunakan Ookla Speedtest CLI untuk pengujian kecepatan internet.

### A. PC / Laptop (Linux x86_64)

Download binary:

```bash
curl -LO https://install.speedtest.net/app/cli/ookla-speedtest-1.2.0-linux-x86_64.tgz
```

Ekstrak dan install:

```bash
tar xzf ookla-speedtest-1.2.0-linux-x86_64.tgz
sudo install -m 755 speedtest /usr/local/bin/speedtest
```

Hapus file sementara:

```bash
rm -f speedtest ookla-speedtest-*.tgz
```

Tes Speedtest dan setujui lisensi:

```bash
speedtest --accept-license --accept-gdpr
```

Jika diminta, ketik `YES` lalu tekan Enter.

### B. STB / Perangkat Linux ARM64 (aarch64)

Download binary:

```bash
curl -LO https://install.speedtest.net/app/cli/ookla-speedtest-1.2.0-linux-aarch64.tgz
```

Ekstrak dan install:

```bash
tar xzf ookla-speedtest-1.2.0-linux-aarch64.tgz
sudo install -m 755 speedtest /usr/local/bin/speedtest
```

Hapus file sementara:

```bash
rm -f speedtest ookla-speedtest-*.tgz
```

Tes Speedtest dan setujui lisensi:

```bash
speedtest --accept-license --accept-gdpr
```

Jika diminta, ketik `YES` lalu tekan Enter.

## 3. Installation RioOS

Masuk ke folder project:

```bash
cd RioOS
```

Buat virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## 4. Konfigurasi Admin

Atur username:

```bash
export RIOOS_ADMIN_USERNAME="admin"
```

Atur password:

```bash
export RIOOS_ADMIN_PASSWORD="PASSWORD_KAMU"
```

Generate Secret Key:

```bash
export RIOOS_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

## 5. Jalankan RioOS

```bash
python3 app.py
```

Buka browser:

```text
http://127.0.0.1:5000/login
```

## 6. RioOS Features

- Dashboard Server Monitoring
- CPU, RAM, Disk Monitoring
- Internet Speedtest (Ookla)
- File Sharing
- App Manager
- Network Guardian
- Network Scanning (arp-scan)
- Firewall Management (iptables)
- Task Manager
- Terminal Management
- Admin & User Login (RBAC)
- User Access Management

## 7. Access Control

**ADMIN**

- Akses seluruh fitur RioOS.
- Mengelola aplikasi, jaringan, dan server.
- Mengelola akun pengguna dan hak akses.

**USER**

- Dashboard Monitoring.
- Speedtest.
- Share Files.

## 8. Security

- Password Hashing
- Session-based Authentication
- Role-Based Access Control (RBAC)
- Admin-only API Protection

**Developer:** Rio-Project 
Kami akan selalu memperbarui project ini~

Jika menemukan bug atau eror segera hubungi suport kami di bawah ini

EMAIL:marioyosefsoegiharto@gmail.com

WHATSSAPP:+6283891828258

TELEGRAM:@rioprojectofficial

