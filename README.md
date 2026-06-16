# ConvertMePls — Python SDK

Convert and compress images, video and audio through the [ConvertMePls](https://convertmepls.com) API. Standard library only — no dependencies.

```bash
pip install convertmepls
```

```python
from convertmepls import ConvertMePls

gc = ConvertMePls(api_key="gck_live_…")          # or set CONVERTMEPLS_API_KEY

# Convert a file (format inferred from the extension)
gc.convert_file("photo.heic", "jpeg", out="photo.jpg")

# Convert raw bytes
job = gc.convert(open("clip.mov", "rb").read(), target="mp4", source="mov")
data = gc.download(job.download_url)

# Compress (re-encode the same format, smaller) — light | balanced | strong
gc.compress_file("photo.jpg", out="photo.min.jpg", level="strong")

# Resize + quality options
gc.convert_file("big.png", "webp", out="thumb.webp", options={"width": 800, "quality": 80})

# Discover supported formats/pairs
print(len(gc.formats()["formats"]), "formats")
```

Without an API key, requests run against the free per-IP tier. With a key, usage
counts toward your plan's monthly quota (see your dashboard). Self-hosting? Pass
`base_url="https://api.your-domain.com"`.
