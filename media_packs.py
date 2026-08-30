"""KUDBEE Media Pack Architecture

Manages swappable capability packs on external storage.

Layout:
    /mnt/packs/
    ├── cinema-v1/
    │   ├── manifest.yaml
    │   ├── models/
    │   │   ├── flux-1-dev/     (~24GB - photorealistic images)
    │   │   ├── ltx-2.3/         (~22GB - video + audio)
    │   │   └── ace-step-1.5/   (~19GB - music)
    │   └── tools/
    └── research-v1/
        ├── manifest.yaml
        └── models/
"""

import os
import json
import yaml
import subprocess
from pathlib import Path
from typing import Optional


class PackManager:
    def __init__(self, packs_dir: str = "/mnt/packs"):
        self.packs_dir = packs_dir
        os.makedirs(packs_dir, exist_ok=True)
    
    def create_pack(self, pack_id: str, name: str, capabilities: list[str], models: list[dict]) -> str:
        pack_path = os.path.join(self.packs_dir, pack_id)
        os.makedirs(os.path.join(pack_path, "models"), exist_ok=True)
        os.makedirs(os.path.join(pack_path, "tools"), exist_ok=True)
        
        manifest = {
            "pack": {"id": pack_id, "name": name, "version": "1.0.0"},
            "capabilities": capabilities,
            "models": models,
        }
        
        with open(os.path.join(pack_path, "manifest.yaml"), "w") as f:
            yaml.dump(manifest, f, default_flow_style=False)
        
        return pack_path
    
    def scan(self) -> dict:
        packs = {}
        if not os.path.exists(self.packs_dir):
            return packs
        
        for entry in os.listdir(self.packs_dir):
            manifest_path = os.path.join(self.packs_dir, entry, "manifest.yaml")
            if os.path.exists(manifest_path):
                with open(manifest_path) as f:
                    packs[entry] = yaml.safe_load(f)
        return packs
    
    def get_model_path(self, pack_id: str, model_id: str) -> Optional[str]:
        path = os.path.join(self.packs_dir, pack_id, "models", model_id)
        return path if os.path.exists(path) else None


def create_cinema_pack():
    pm = PackManager()
    
    models = [
        {"id": "flux-1-dev", "capability": "image.generate", "vram_gb": 24,
         "source": "huggingface:black-forest-labs/FLUX.1-dev"},
        {"id": "ltx-2.3", "capability": "video.generate", "vram_gb": 48,
         "source": "huggingface:Lightricks/LTX-2.3"},
        {"id": "ace-step-1.5", "capability": "audio.music", "vram_gb": 8,
         "source": "local:/opt/kudbee/models/acestep"},
    ]
    
    path = pm.create_pack(
        "cinema-v1", "KUDBEE Cinema Pack",
        ["image.generate", "video.generate", "audio.music", "character.animate"],
        models
    )
    return path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 media_packs.py <create|scan>")
        sys.exit(1)
    
    if sys.argv[1] == "create":
        path = create_cinema_pack()
        print(f"Created Cinema Pack at: {path}")
    elif sys.argv[1] == "scan":
        pm = PackManager()
        print(json.dumps(pm.scan(), indent=2))
