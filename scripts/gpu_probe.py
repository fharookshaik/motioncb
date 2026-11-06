"""Measure training batch fit for the reference-shaped U-Net on CUDA."""

import argparse
import gc
import json

import segmentation_models_pytorch as smp
import torch
import torch.nn.functional as F
import yaml


def probe_batch(batch: int, channels: int, size: int, dtype: torch.dtype) -> tuple[bool, int]:
    """Run one AdamW training step; include optimizer state in peak memory."""
    model = optimizer = inputs = labels = logits = loss = None
    try:
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        model = smp.Unet(encoder_name="resnet50", encoder_weights=None, in_channels=channels, classes=1).cuda()
        optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4)
        inputs = torch.randn(batch, channels, size, size, device="cuda")
        labels = torch.randint(0, 2, (batch, 1, size, size), device="cuda").float()
        scaler = torch.amp.GradScaler("cuda", enabled=dtype == torch.float16)
        with torch.autocast("cuda", dtype=dtype):
            logits = model(inputs)
            probabilities = logits.float().sigmoid()
            dice = 1 - (2 * (probabilities * labels).sum() + 1e-7) / (probabilities.sum() + labels.sum() + 1e-7)
            loss = (F.binary_cross_entropy_with_logits(logits.float(), labels) + dice) / 2
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        torch.cuda.synchronize()
        return True, torch.cuda.max_memory_allocated()
    except torch.OutOfMemoryError:
        return False, torch.cuda.max_memory_allocated()
    finally:
        del model, optimizer, inputs, labels, logits, loss
        gc.collect()
        torch.cuda.empty_cache()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Reference YAML configuration")
    args = parser.parse_args()
    with open(args.config, encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable; GPU probe cannot run")
    device = torch.cuda.get_device_properties(0)
    bf16 = torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if bf16 else torch.float16
    channels, size = len(config["imagery"]["bands"]), config["chips"]["size_px"]
    results = []
    for batch in range(1, 17):
        ok, peak = probe_batch(batch, channels, size, dtype)
        results.append({"batch": batch, "fits": ok, "peak_allocated_bytes": peak})
        if not ok:
            break
    print(json.dumps({"gpu": device.name, "vram_bytes": device.total_memory, "bf16": bf16,
                      "precision": str(dtype), "channels": channels, "size_px": size,
                      "max_batch_capped_16": max((r["batch"] for r in results if r["fits"]), default=0),
                      "trials": results}, indent=2))


if __name__ == "__main__":
    main()
