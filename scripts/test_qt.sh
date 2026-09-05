#!/bin/bash
echo "Testing Qt window creation..."
QT_QPA_PLATFORM=xcb python3 -c "
from PyQt6.QtWidgets import QApplication, QWidget, QLabel
from PyQt6.QtCore import Qt
import sys
app = QApplication(sys.argv)
w = QWidget()
w.setWindowTitle('JARVIS TEST')
w.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
w.setStyleSheet('background: rgba(0,6,10,200);')
w.resize(400, 300)
w.show()
print('Window shown')
sys.exit(app.exec())
" 2>&1 &
PID=$!
echo "Started PID $PID"
sleep 5
echo "Checking..."
wmctrl -l 2>/dev/null | grep -i "test" || echo "No TEST window in wmctrl"
xwininfo -root -tree 2>/dev/null | grep -i "test" || echo "No TEST window in xwininfo"
echo "Process alive:"
ps aux | grep "python3 -c" | grep -v grep || echo "Process dead"
kill $PID 2>/dev/null
wait $PID 2>/dev/null
