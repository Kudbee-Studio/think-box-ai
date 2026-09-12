#!/usr/bin/env python3
"""Deterministic mock vLLM server for think-v2 burst testing.

Implements OpenAI-compatible API with deterministic responses.
Runs on localhost:8001 with HTTP/1.0 support.

Endpoints:
- GET /v1/models - Returns model list
- POST /v1/chat/completions - Chat completions (streaming & non-streaming)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Generator
from urllib.parse import urlparse


@dataclass
class MockConfig:
    model: str = "openai/gpt-oss-20b"
    max_model_len: int = 8192
    version: str = "mock-1.0"


def _tokenize(text: str):
    """Tokenize text for deterministic matching."""
    for word in text.lower().split():
        word = ''.join(c for c in word if c.isalnum())
        if word:
            yield word


class MockVLLMServer:
    """Deterministic mock vLLM server with deterministic responses."""
    
    def __init__(self, config: MockConfig | None = None):
        self.config = config or MockConfig()
        self._request_count = 0
    
    def handle_models(self) -> dict:
        """Handle /v1/models endpoint."""
        return {
            "object": "list",
            "data": [
                {
                    "id": self.config.model,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "kudbee-mock",
                    "max_model_len": self.config.max_model_len,
                }
            ]
        }
    
    def _generate_deterministic_response(self, messages: list[dict]) -> tuple[str, str]:
        """Generate deterministic response based on input messages."""
        user_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_content = msg.get("content", "")
                break
        
        content_lower = str(messages).lower()
        
        if "2+2" in str(messages).lower() or "2+2" in user_content:
            return "4", "2 + 2 = 4. Adding two plus two equals four."
        elif "capital of france" in str(messages).lower():
            return "Paris", "Paris is the capital city of France."
        elif "crdt" in str(messages).lower():
            return "Conflict-free Replicated Data Type", "CRDT stands for Conflict-free Replicated Data Type, a data structure that automatically merges concurrent updates."
        elif "ssm" in str(messages).lower() and "aws" in str(messages).lower():
            return "AWS Systems Manager", "SSM in AWS context stands for Systems Manager, which provides operational insights and management capabilities for AWS resources."
        else:
            return "This is a deterministic mock response from the mock vLLM server.", "This is a deterministic mock response. The mock server generates deterministic responses based on the input prompt."
    
    def create_chat_completion(self, messages: list[dict], stream: bool = False, model: str | None = None) -> dict:
        """Generate a non-streaming chat completion response."""
        self._request_count += 1
        model = model or "openai/gpt-oss-20b"
        
        content, reasoning = self._generate_deterministic_response(messages)
        
        response = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "reasoning": reasoning
                },
                "finish_reason": "stop",
                "index": 0
            }],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 50,
                "total_tokens": 100
            }
        }
        return response
    
    def _generate_streaming_chunks(self, messages: list[dict], model: str | None = None) -> Generator[dict, None, None]:
        """Generate streaming response chunks for SSE."""
        self._request_count += 1
        model = model or "openai/gpt-oss-20b"
        
        content, reasoning = self._generate_deterministic_response(messages)
        request_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())
        
        # Content chunks
        for i in range(0, len(content), 10):
            chunk = {
                "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "openai/gpt-oss-20b",
                "choices": [{
                    "index": 0,
                    "delta": {"content": content[i:i+10]},
                    "finish_reason": None
                }]
            }
            yield chunk
        
        # Reasoning chunks
        for i in range(0, len(reasoning), 10):
            yield {
                "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "openai/gpt-oss-20b",
                "choices": [{
                    "index": 0,
                    "delta": {"reasoning": reasoning[i:i+10]},
                    "finish_reason": None
                }]
            }
        
        # Final chunk
        yield {
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "openai/gpt-oss-20b",
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }


class MockVLLMHandler(BaseHTTPRequestHandler):
    """HTTP request handler for mock vLLM server."""
    
    server_version = "MockVLLM/1.0"
    mock_server = MockVLLMServer()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/v1/models":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = self.mock_server.handle_models()
            self.wfile.write(json.dumps(response).encode())
            return
        
        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
            return
        
        self.send_error(404)
    
    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            request_data = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        
        # Check authorization
        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            self.send_error(401, "Unauthorized")
            return
        
        # Parse request
        messages = request_data.get('messages', [])
        stream = request_data.get('stream', False)
        model = request_data.get('model', 'openai/gpt-oss-20b')
        
        if stream:
            self._send_streaming_response(messages, model)
        else:
            response = self.mock_server.create_chat_completion(
                messages,
                stream=False,
                model=model
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
    
    def _send_streaming_response(self, messages: list[dict], model: str):
        """Send Server-Sent Events (SSE) streaming response."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        
        for chunk in self.mock_server._generate_streaming_chunks(messages, model):
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            time.sleep(0.01)
        
        self.wfile.write(b"data: [DONE]\n\n")


def run_server(host: str = "127.0.0.1", port: int = 8001):
    """Run the mock vLLM server."""
    server = HTTPServer(("127.0.0.1", 8001), MockVLLMHandler)
    print(f"Mock vLLM server starting on http://127.0.0.1:8001")
    print(f"Models endpoint: http://127.0.0.1:8001/v1/models")
    print(f"Chat completions: http://127.0.0.1:8001/v1/chat/completions")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock vLLM server for think-v2 burst testing")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind to")
    args = parser.parse_args()
    
    run_server(args.host, args.port)