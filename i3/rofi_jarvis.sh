#!/bin/bash
INPUT=$(rofi -dmenu -p "JARVIS" -lines 0)
if [ -n "$INPUT" ]; then
    curl -s -X POST http://localhost:8765/command -d "{\"text\": \"$INPUT\"}"
fi
