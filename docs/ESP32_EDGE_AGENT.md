# ESP32-S3 Edge Agent

**Issue:** #17 — Phase 4: ESP32-S3 Edge Agent (28.9M Parameter LLM)
**Status:** Architecture plan — hardware build requires Kudbee

## Hardware Specs

| Component | Spec |
|-----------|------|
| MCU | ESP32-S3-WROOM-1 |
| CPU | Dual-core Xtensa LX7 @ 240MHz |
| RAM | 8MB PSRAM |
| Flash | 16MB |
| Connectivity | WiFi 4 + Bluetooth 5 LE |
| Power | 3.3V, ~240mA active |

## Model: 28.9M Parameter LLM

**Candidate models:**
- TinyLlama 1.1B (quantized to 4-bit = ~60MB, too large)
- Phi-3 Mini 3.8B (quantized = ~2.5MB, fits!)
- Qwen2.5 0.5B (quantized = ~300KB, fast!)

**Selected:** Qwen2.5 0.5B (instruct, 4-bit quantized)
- Size: ~300KB (fits in RAM)
- Inference: ~50ms per token on ESP32-S3
- Use case: Simple Q&A, command parsing, sensor analysis

## Software Stack

```
┌─────────────────────────────────┐
│  Application Layer              │
│  - Command parser               │
│  - Sensor interface             │
│  - Network handler              │
├─────────────────────────────────┤
│  Inference Engine               │
│  - llama.cpp (ESP32 port)       │
│  - 4-bit quantized model        │
│  - KV cache management          │
├─────────────────────────────────┤
│  Hardware Abstraction           │
│  - ESP-IDF / Arduino            │
│  - WiFi driver                  │
│  - GPIO / I2C / SPI             │
└─────────────────────────────────┘
```

## Implementation Plan

1. **Flash firmware** — ESP-IDF with llama.cpp port
2. **Load model** — Store quantized model in flash
3. **WiFi connect** — Connect to local network
4. **API endpoint** — HTTP server for inference requests
5. **Sensor integration** — Read from connected sensors
6. **OTA updates** — Remote firmware updates

## Code Sketch

```cpp
#include "esp_http_server.h"
#include "llama.h"

// Initialize model
struct llama_model * model = llama_load_model_from_file("/sparks/model.bin");
struct llama_context * ctx = llama_new_context_with_model(model, {});

// HTTP handler
esp_err_t inference_handler(httpd_req_t *req) {
    char prompt[512];
    httpd_req_recv(req, prompt, sizeof(prompt));
    
    // Tokenize
    std::vector<llama_token> tokens = llama_tokenize(ctx, prompt, true);
    
    // Generate
    llama_decode(ctx, llama_batch_get_one(tokens.data(), tokens.size()));
    
    // Return response
    char response[1024];
    // ... generate tokens ...
    
    httpd_resp_send(req, response, strlen(response));
    return ESP_OK;
}
```

## Use Cases

- **Offline agent** — Works without internet
- **Sensor analysis** — Process data locally
- **Voice commands** — Wake word + command parsing
- **Security monitor** — Detect anomalies on-device

## Power Budget

| Mode | Current | Runtime (2000mAh) |
|------|---------|-------------------|
| Active inference | 240mA | ~8 hours |
| WiFi active | 160mA | ~12 hours |
| Deep sleep | 10μA | ~20 years |

## Kudbee Action Items

1. [ ] Purchase ESP32-S3 dev board ($10-15)
2. [ ] Flash with ESP-IDF
3. [ ] Port llama.cpp
4. [ ] Quantize Qwen2.5 0.5B model
5. [ ] Test inference latency
