"""
Replicate client for BC pellicle image analysis.
Ported from AI Designer.yml code node; adapted for local files instead of Dify file IDs.
"""
import asyncio
import base64
from pathlib import Path

import httpx

REPLICATE_API = "https://api.replicate.com/v1/predictions"


def _fmt(x, nd=2):
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return "n/a"


async def run_prediction(image_path: str | Path, rep_token: str, rep_version: str) -> str:
    """
    Submit image to Replicate, poll for result, return formatted prediction text.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return f"ERROR: Image file not found ({image_path.name})."

    img_bytes = image_path.read_bytes()
    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
    }
    mime = mime_map.get(image_path.suffix.lower(), "image/jpeg")
    image_input = f"data:{mime};base64,{base64.b64encode(img_bytes).decode()}"

    headers = {
        "Authorization": f"Bearer {rep_token}",
        "Content-Type": "application/json",
        "Prefer": "wait=60",
    }
    payload = {
        "version": rep_version,
        "input": {"image": image_input},
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(REPLICATE_API, headers=headers, json=payload)
        if r.status_code >= 400:
            return f"ERROR: Replicate request failed ({r.status_code})\n{r.text[:800]}"

        pred = r.json()

        # If Prefer: wait didn't resolve it, poll
        poll_url = pred.get("urls", {}).get("get")
        if pred.get("status") not in ("succeeded", "failed", "canceled") and poll_url:
            for _ in range(30):
                await asyncio.sleep(2)
                rr = await client.get(poll_url, headers=headers, timeout=30)
                rr.raise_for_status()
                pred = rr.json()
                if pred.get("status") in ("succeeded", "failed", "canceled"):
                    break

    if pred.get("status") != "succeeded":
        return f"ERROR: Prediction {pred.get('status', 'unknown')}.\n{pred}"

    out = pred.get("output", {})
    cls = out.get("classification", {})
    reg = out.get("regression", {})

    return (
        f"Predicted class: {cls.get('predicted_class', 'unknown')}\n"
        f"Top probabilities: {cls.get('probabilities', {})}\n\n"
        f"Mechanical properties:\n"
        f"- Tensile strength (MPa): {_fmt(reg.get('tensile_strength_mpa'))}\n"
        f"- Elongation (%): {_fmt(reg.get('elongation_pct'))}\n"
        f"- Stiffness index: {_fmt(reg.get('stiffness_index'), 3)}\n"
        f"- Uniformity score: {_fmt(reg.get('uniformity_score'), 3)}"
    )
