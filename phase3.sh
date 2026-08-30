#!/bin/bash
echo "=== PHASE 3: SPECIALIZED THINK BOXES ==="

echo "1. Director Box - Shot List..."
curl -s -X POST http://localhost:9090/create \
  -H "Content-Type: application/json" \
  -d '{"type": "director", "task": "Create shot list for POWER PLAY film"}'

echo ""
echo "2. Music Composer..."
curl -s -X POST http://localhost:9090/create \
  -H "Content-Type: application/json" \
  -d '{"type": "music", "task": "Generate 3 music tracks for film"}'

echo ""
echo "3. Character Design..."
curl -s -X POST http://localhost:9090/create \
  -H "Content-Type: application/json" \
  -d '{"type": "image-gen", "task": "Generate character references"}'

echo ""
echo "4. Video Generation..."
curl -s -X POST http://localhost:9090/create \
  -H "Content-Type: application/json" \
  -d '{"type": "video-gen", "task": "Generate video clips for key scenes"}'

echo ""
echo "5. Sound Design..."
curl -s -X POST http://localhost:9090/create \
  -H "Content-Type: application/json" \
  -d '{"type": "voice", "task": "Generate sound effects"}'

echo ""
echo "6. Editor..."
curl -s -X POST http://localhost:9090/create \
  -H "Content-Type: application/json" \
  -d '{"type": "director", "task": "Create editing timeline"}'

echo ""
echo "7. Jury/Quality Control..."
curl -s -X POST http://localhost:9090/create \
  -H "Content-Type: application/json" \
  -d '{"type": "director", "task": "Evaluate screenplay quality"}'

echo ""
echo "8. Production Coordinator..."
curl -s -X POST http://localhost:9090/create \
  -H "Content-Type: application/json" \
  -d '{"type": "script-writer", "task": "Create production schedule"}'

echo ""
echo "Phase 3 Complete!"
