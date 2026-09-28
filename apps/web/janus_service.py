"""CPU-only Janus-Pro service for image understanding and generation."""

import base64
import binascii
import io
import os
import threading
from typing import Any

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM

from janus.models import MultiModalityCausalLM, VLChatProcessor

MODEL_ID = os.environ.get("JANUS_MODEL", "deepseek-ai/Janus-Pro-1B")
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_PROMPT_LENGTH = 4000
DEVICE = torch.device("cpu")
INFERENCE_LOCK = threading.Lock()
torch.set_num_threads(max(1, int(os.environ.get("OMP_NUM_THREADS", "2"))))

app = FastAPI(title="Janus CPU Image Service")
processor: VLChatProcessor | None = None
model: MultiModalityCausalLM | None = None
load_error: str | None = None


class ImageRequest(BaseModel):
    image_base64: str = Field(min_length=1, max_length=MAX_IMAGE_BYTES * 2)
    prompt: str = Field(default="Describe this image.", max_length=MAX_PROMPT_LENGTH)


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=MAX_PROMPT_LENGTH)


def load_model() -> tuple[VLChatProcessor, MultiModalityCausalLM]:
    global processor, model, load_error
    if processor is not None and model is not None:
        return processor, model
    try:
        loaded_processor = VLChatProcessor.from_pretrained(MODEL_ID)
        loaded_model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            trust_remote_code=True,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
        ).to(DEVICE).eval()
        processor = loaded_processor
        model = loaded_model
        load_error = None
        return loaded_processor, loaded_model
    except Exception as error:
        load_error = str(error)
        raise


def decode_image(image_base64: str) -> Image.Image:
    try:
        raw = base64.b64decode(image_base64, validate=True)
    except (ValueError, binascii.Error) as error:
        raise HTTPException(status_code=400, detail="Invalid base64 image") from error
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 12 MB limit")
    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as error:
        raise HTTPException(status_code=400, detail="Unsupported or invalid image") from error
    if image.width * image.height > 20_000_000:
        raise HTTPException(status_code=413, detail="Image dimensions exceed the limit")
    return image


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok" if model is not None else "loading" if load_error is None else "error",
        "ready": model is not None,
        "model": MODEL_ID,
        "device": "cpu",
        "error": load_error,
    }


@app.post("/analyze")
@torch.inference_mode()
def analyze(request: ImageRequest) -> dict[str, str]:
    image = decode_image(request.image_base64)
    with INFERENCE_LOCK:
        try:
            active_processor, active_model = load_model()
            conversation = [
                {
                    "role": "<|User|>",
                    "content": f"<image_placeholder>\n{request.prompt.strip()}",
                    "images": [image],
                },
                {"role": "<|Assistant|>", "content": ""},
            ]
            inputs = active_processor(
                conversations=conversation,
                images=[image],
                force_batchify=True,
            ).to(DEVICE)
            embeddings = active_model.prepare_inputs_embeds(**inputs)
            outputs = active_model.language_model.generate(
                inputs_embeds=embeddings,
                attention_mask=inputs.attention_mask,
                pad_token_id=active_processor.tokenizer.eos_token_id,
                bos_token_id=active_processor.tokenizer.bos_token_id,
                eos_token_id=active_processor.tokenizer.eos_token_id,
                max_new_tokens=256,
                do_sample=False,
                use_cache=True,
            )
            answer = active_processor.tokenizer.decode(
                outputs[0].cpu().tolist(), skip_special_tokens=True
            ).strip()
            return {"answer": answer}
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"Janus inference failed: {error}") from error


@app.post("/generate")
@torch.inference_mode()
def generate(request: GenerateRequest) -> dict[str, str]:
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    with INFERENCE_LOCK:
        try:
            active_processor, active_model = load_model()
            conversation = [
                {"role": "User", "content": request.prompt.strip()},
                {"role": "Assistant", "content": ""},
            ]
            formatted = active_processor.apply_sft_template_for_multi_turn_prompts(
                conversations=conversation,
                sft_format=active_processor.sft_format,
                system_prompt="",
            )
            prompt = formatted + active_processor.image_start_tag
            input_ids = torch.tensor(
                active_processor.tokenizer.encode(prompt), dtype=torch.int32, device=DEVICE
            )
            parallel_size = 1
            tokens = input_ids.repeat(parallel_size * 2, 1)
            tokens[1, 1:-1] = active_processor.pad_id
            inputs_embeds = active_model.language_model.get_input_embeddings()(tokens)
            generated_tokens = torch.zeros((parallel_size, 576), dtype=torch.int32, device=DEVICE)
            outputs = None

            for index in range(generated_tokens.shape[1]):
                outputs = active_model.language_model.model(
                    inputs_embeds=inputs_embeds,
                    use_cache=True,
                    past_key_values=outputs.past_key_values if outputs is not None else None,
                )
                logits = active_model.gen_head(outputs.last_hidden_state[:, -1, :])
                conditional, unconditional = logits[0::2], logits[1::2]
                probabilities = torch.softmax(unconditional + 5.0 * (conditional - unconditional), dim=-1)
                next_token = torch.multinomial(probabilities, num_samples=1)
                generated_tokens[:, index] = next_token.squeeze(-1)
                paired_token = next_token.repeat(1, 2).reshape(-1)
                inputs_embeds = active_model.prepare_gen_img_embeds(paired_token).unsqueeze(1)

            decoded = active_model.gen_vision_model.decode_code(
                generated_tokens,
                shape=[parallel_size, 8, 24, 24],
            )
            pixels = decoded.float().cpu().numpy().transpose(0, 2, 3, 1)
            pixels = np.clip((pixels + 1) * 127.5, 0, 255).astype(np.uint8)
            output = io.BytesIO()
            Image.fromarray(pixels[0]).save(output, format="PNG")
            return {"image_base64": base64.b64encode(output.getvalue()).decode("ascii")}
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"Janus generation failed: {error}") from error