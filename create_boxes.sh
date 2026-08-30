#!/bin/bash
echo "=== CREATING SPECIALIZED THINK BOXES ==="

echo "1. Script Writer (GPT-120B)..."
curl -s -X POST http://localhost:9090/create \
  -H "Content-Type: application/json" \
  -d '{"type": "script-writer", "task": "Write a 90-second trailer about a man in his car"}'

echo ""
echo "2. Director Box..."
curl -s -X POST http://localhost:9090/create \
  -H "Content-Type: application/json" \
  -d '{"type": "director", "task": "Create storyboard"}'

echo ""
echo "3. Trend Researcher..."
curl -s -X POST http://localhost:9090/create \
  -H "Content-Type: application/json" \
  -d '{"type": "trend-researcher", "task": "Find trending TikTok products"}'

echo ""
echo "4. Music Composer..."
curl -s -X POST http://localhost:9090/create \
  -H "Content-Type: application/json" \
  -d '{"type": "music", "task": "Generate soundtrack"}'

echo ""
echo "5. Image Generator..."
curl -s -X POST http://localhost:9090/create \
  -H "Content-Type: application/json" \
  -d '{"type": "image-gen", "task": "Generate character"}'

echo ""
echo "6. Video Generator..."
curl -s -X POST http://localhost:9090/create \
  -H "Content-Type: application/json" \
  -d '{"type": "video-gen", "task": "Generate car scene"}'

echo ""
echo "=== FINAL STATUS ==="
curl -s http://localhost:9090/status
echo ""
