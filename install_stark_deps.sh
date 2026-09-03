#!/bin/bash
# Run as: sudo bash install_stark_deps.sh
echo "=== STARK OS: Installing Core Dependencies ==="
sudo pacman -Syu --noconfirm \
    python python-pip python-virtualenv \
    xdotool xclip xsel wmctrl scrot maim ffmpeg \
    xorg-xvfb xorg-xprop xorg-xwininfo \
    networkmanager nm-connection-editor \
    pipewire pipewire-pulse wireplumber \
    brightnessctl lm_sensors htop iotop \
    iptables nftables ufw \
    docker docker-compose \
    git curl wget jq \
    pandoc texlive-basic texlive-latexextra texlive-fontsrecommended \
    inotify-tools \
    rofi dmenu \
    polybar i3blocks \
    btrfs-progs snapper \
    intel-undervolt \
    acpi upower \
    linux-headers \
    base-devel
if ! command -v yay &> /dev/null; then
    sudo pacman -S --noconfirm git base-devel
    git clone https://aur.archlinux.org/yay.git /tmp/yay
    cd /tmp/yay && makepkg -si --noconfirm
fi
yay -Syu --noconfirm \
    google-chrome \
    spotify \
    nvidia-utils \
    python-pyqt6 \
    python-pyqt6-webengine
pip install --upgrade pip
pip install \
    PyQt6 PyQt6-WebEngine \
    playwright browser-use \
    chromadb sentence-transformers \
    psutil GPUtil pynvml \
    scapy frida-tools \
    docker \
    cryptography \
    requests httpx aiohttp \
    beautifulsoup4 lxml \
    pypandoc genanki \
    pydantic \
    apscheduler \
    watchdog \
    pynput evdev \
    mediapipe \
    yt-dlp \
    openai \
    pyserial \
    python-xlib \
    i3ipc
playwright install chromium
playwright install-deps
sudo systemctl enable docker
sudo systemctl enable NetworkManager
sudo systemctl enable ufw
sudo tee /etc/modules-load.d/stark.conf << 'EOF'
coretemp
k10temp
nvidia
i2c-dev
EOF
sudo sensors-detect --auto
echo "=== STARK OS: All dependencies installed ==="
