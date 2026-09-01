# ElevenLabs MCP Voice Plugin

**Issue:** #10 — Phase 2: ElevenLabs MCP Voice Plugin
**Status:** Configuration ready — needs API key from Kudbee

## Configuration

Add to your Upstash Box MCP servers or local MCP config:

```json
{
  "name": "elevenlabs-voice",
  "source": "npm",
  "package_or_url": "@elevenlabs/mcp-server@1.0.0",
  "enabled": true,
  "env": {
    "ELEVENLABS_API_KEY": "sk_your_api_key_here"
  }
}
```

## Capabilities

- **Text-to-Speech** — Convert text to natural voice
- **Voice Cloning** — Clone voices from samples
- **Speech-to-Text** — Transcribe audio
- **Sound Effects** — Generate audio effects

## Integration Ideas

1. **Voice Narration** — Read findings aloud
2. **Audio Inscriptions** — Inscribe audio to Doginals
3. **Accessibility** — Screen reader support
4. **Notifications** — Voice alerts for job completion

## Setup Steps

1. Get API key from [elevenlabs.io](https://elevenlabs.io)
2. Add to MCP server config
3. Restart the box
4. Test with: "Convert this text to speech: Woof!"
