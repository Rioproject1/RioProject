# RioProject
RioOS Dashboard Server Management
TATA CARA INSTALL OS BY RIO MWEHEHE 

TAHAP 1:
# 1. Update sistem & install python, tmux (biar bisa jalan di background)
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv tmux curl -y

# 2. Install Ookla Speedtest (KHUSUS ARM64/STB)
curl -LO https://install.speedtest.net/app/cli/ookla-speedtest-1.2.0-linux-aarch64.tgz
tar xzf ookla-speedtest-1.2.0-linux-aarch64.tgz
sudo install -m 755 speedtest /usr/local/bin/speedtest

# 3. Tes Speedtest (Ketik YES kalau disuruh setuju)
speedtest

# 4. Bikin folder project & masuk ke dalamnya
mkdir rio-os && cd rio-os

# 5. Bikin virtual environment (venv) & aktifin
python3 -m venv venv
source venv/bin/activate

# 6. Install library Python yang dibutuhin RioOS
pip install flask psutil requests werkzeug

TAHAP 2:
# Bikin sesi tmux
tmux new -s rio-server

# Aktifin venv (kalau belum)
source venv/bin/activate

# Jalanin server
python3 app.py

# (Setelah server nyala) Tekan CTRL+B, lepas, lalu tekan D
# (Sekarang lo bisa cabut SSH/terminal, server tetep jalan di background)


# tambahan sudo apt update
sudo apt install arp-scan iptables -y  

# sudo visudo biar anu sudo whoami     

# cd ~/RioOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
