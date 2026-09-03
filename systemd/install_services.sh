#!/bin/bash
echo "=== Installing JARVIS systemd services ==="
mkdir -p ~/.config/systemd/user/
cp systemd/jarvis-core.service ~/.config/systemd/user/
cp systemd/jarvis-sentinel.service ~/.config/systemd/user/
cp systemd/jarvis-visual-memory.service ~/.config/systemd/user/
sed -i "s|%h|$HOME|g" ~/.config/systemd/user/jarvis-*.service
sed -i "s|%U|$(id -u)|g" ~/.config/systemd/user/jarvis-*.service
sed -i "s|%i|$(whoami)|g" ~/.config/systemd/user/jarvis-*.service
systemctl --user daemon-reload
systemctl --user enable jarvis-core
systemctl --user enable jarvis-sentinel
systemctl --user enable jarvis-visual-memory
echo "=== JARVIS services installed ==="
