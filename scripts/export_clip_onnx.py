"""
Export CLIP ViT-B/32 model to ONNX format.

Produces two ONNX files (vision + text encoder) and saves the processor.
This script runs in the Docker build stage (with torch), so the production
image only needs onnxruntime (no torch).

Usage:
    python scripts/export_clip_onnx.py --model openai/clip-vit-base-patch32 --output /models
"""

import argparse
import os

import torch
import torch.nn as nn
from transformers import CLIPModel, CLIPProcessor


class CLIPImageEncoder(nn.Module):
    """Wrapper that exposes get_image_features as a simple forward()."""

    def __init__(self, clip_model: CLIPModel) -> None:
        super().__init__()
        self.clip_model = clip_model

    def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
        return self.clip_model.get_image_features(pixel_values=pixel_values)


class CLIPTextEncoder(nn.Module):
    """Wrapper that exposes get_text_features as a simple forward()."""

    def __init__(self, clip_model: CLIPModel) -> None:
        super().__init__()
        self.clip_model = clip_model

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        return self.clip_model.get_text_features(
            input_ids=input_ids, attention_mask=attention_mask
        )


def export(model_name: str, output_dir: str) -> None:
    print(f"Loading model: {model_name}")
    model = CLIPModel.from_pretrained(model_name)
    processor = CLIPProcessor.from_pretrained(model_name)
    model.eval()

    os.makedirs(output_dir, exist_ok=True)

    # Save processor (tokenizer + image processor config)
    processor_dir = os.path.join(output_dir, "processor")
    processor.save_pretrained(processor_dir)
    print(f"Processor saved to {processor_dir}")

    # Export vision encoder
    vision_path = os.path.join(output_dir, "clip_vision.onnx")
    image_encoder = CLIPImageEncoder(model)
    dummy_pixel_values = torch.randn(1, 3, 224, 224)

    torch.onnx.export(
        image_encoder,
        (dummy_pixel_values,),
        vision_path,
        input_names=["pixel_values"],
        output_names=["image_features"],
        dynamic_axes={
            "pixel_values": {0: "batch"},
            "image_features": {0: "batch"},
        },
        opset_version=18,
    )
    print(f"Vision encoder exported to {vision_path}")

    # Export text encoder
    text_path = os.path.join(output_dir, "clip_text.onnx")
    text_encoder = CLIPTextEncoder(model)
    dummy_input_ids = torch.randint(0, 49408, (1, 77))
    dummy_attention_mask = torch.ones(1, 77, dtype=torch.long)

    torch.onnx.export(
        text_encoder,
        (dummy_input_ids, dummy_attention_mask),
        text_path,
        input_names=["input_ids", "attention_mask"],
        output_names=["text_features"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "sequence"},
            "attention_mask": {0: "batch", 1: "sequence"},
            "text_features": {0: "batch"},
        },
        opset_version=18,
    )
    print(f"Text encoder exported to {text_path}")

    # Print sizes
    for name, path in [("Vision", vision_path), ("Text", text_path)]:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  {name}: {size_mb:.1f} MB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export CLIP to ONNX")
    parser.add_argument("--model", default="openai/clip-vit-base-patch32")
    parser.add_argument("--output", default="/models")
    args = parser.parse_args()
    export(args.model, args.output)
