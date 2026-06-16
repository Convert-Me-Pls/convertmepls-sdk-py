"""ConvertMePls Python SDK — convert and compress files via the ConvertMePls API.

    from convertmepls import ConvertMePls
    gc = ConvertMePls(api_key="gck_live_…")
    gc.convert_file("photo.heic", "jpeg", out="photo.jpg")          # convert
    gc.compress_file("photo.jpg", out="photo.min.jpg", level="strong")  # compress

Zero heavy deps — uses urllib from the standard library.
"""
from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

__version__ = "1.0.0"

DEFAULT_BASE_URL = "https://api.convertmepls.com"

# Monthly conversion quota mapping mirrors the server; the level helper mirrors
# the web app so compression behaves identically across clients.
_IMAGE_Q = {"light": 85, "balanced": 70, "strong": 50}
_VIDEO_CRF = {"light": 24, "balanced": 28, "strong": 32}
_AUDIO_BR = {"light": 192, "balanced": 128, "strong": 96}


class ConvertMePlsError(Exception):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


@dataclass
class Job:
    id: str
    status: str
    download_url: Optional[str] = None
    error: Optional[str] = None


class ConvertMePls:
    def __init__(self, api_key: Optional[str] = None, base_url: str = DEFAULT_BASE_URL, timeout: int = 300):
        self.api_key = api_key or os.environ.get("CONVERTMEPLS_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ---- low-level HTTP -----------------------------------------------------
    def _headers(self, json_body: bool = False) -> dict:
        h = {"accept": "application/json"}
        if self.api_key:
            h["authorization"] = f"Bearer {self.api_key}"
        if json_body:
            h["content-type"] = "application/json"
        return h

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method, headers=self._headers(body is not None))
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = json.loads(e.read()).get("error", "")
            except Exception:
                pass
            raise ConvertMePlsError(f"{method} {path} failed ({e.code}): {detail}", e.code) from None

    # ---- catalog ------------------------------------------------------------
    def formats(self) -> dict:
        """The live format + conversion catalog (GET /formats)."""
        return self._request("GET", "/formats")

    # ---- core ---------------------------------------------------------------
    def _upload(self, data: bytes, filename: str, content_type: str) -> str:
        up = self._request("POST", "/uploads", {"filename": filename, "contentType": content_type, "bytes": len(data)})
        put = urllib.request.Request(up["uploadUrl"], data=data, method="PUT", headers={"content-type": content_type})
        try:
            urllib.request.urlopen(put, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            raise ConvertMePlsError(f"upload PUT failed ({e.code})", e.code) from None
        return up["inputKey"]

    def _await(self, job_id: str, interval: float = 1.5) -> Job:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            time.sleep(interval)
            s = self._request("GET", f"/conversions/{job_id}")
            if s["status"] == "done":
                return Job(job_id, "done", s.get("downloadUrl"))
            if s["status"] == "error":
                raise ConvertMePlsError(s.get("error", "conversion failed"))
        raise ConvertMePlsError("conversion timed out")

    def convert(self, data: bytes, target: str, source: str, *, filename: str = "file",
                content_type: Optional[str] = None, options: Optional[dict] = None) -> Job:
        """Convert raw bytes from `source` to `target`. Returns a finished Job."""
        ct = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        input_key = self._upload(data, filename, ct)
        r = self._request("POST", "/conversions",
                          {"inputKey": input_key, "source": source, "target": target, "options": options or {}})
        if not r.get("jobId"):
            raise ConvertMePlsError("server did not return a job id")
        return self._await(r["jobId"])

    def compress(self, data: bytes, fmt: str, *, level: str = "balanced",
                 filename: str = "file", content_type: Optional[str] = None) -> Job:
        """Compress bytes of format `fmt` (re-encode smaller). level: light|balanced|strong."""
        return self.convert(data, fmt, fmt, filename=filename, content_type=content_type,
                            options=self.compress_options(fmt, level))

    @staticmethod
    def compress_options(fmt: str, level: str = "balanced") -> dict:
        images = {"jpeg", "png", "webp", "avif", "gif", "tiff", "heic"}
        videos = {"mp4", "webm", "mov", "mkv", "avi", "flv", "wmv", "mpeg", "m4v", "3gp", "ogv", "ts", "asf", "f4v"}
        if fmt in images:
            return {"quality": _IMAGE_Q.get(level, 70)}
        if fmt in videos:
            return {"crf": _VIDEO_CRF.get(level, 28)}
        return {"bitrate": _AUDIO_BR.get(level, 128)}

    # ---- convenience: files -------------------------------------------------
    def download(self, url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=self.timeout) as resp:
            return resp.read()

    def convert_file(self, path: str, target: str, *, source: Optional[str] = None,
                     out: Optional[str] = None, options: Optional[dict] = None) -> bytes:
        with open(path, "rb") as f:
            data = f.read()
        src = source or (os.path.splitext(path)[1].lstrip(".").lower() or "")
        if src == "jpg":
            src = "jpeg"
        job = self.convert(data, target, src, filename=os.path.basename(path), options=options)
        result = self.download(job.download_url) if job.download_url else b""
        if out:
            with open(out, "wb") as f:
                f.write(result)
        return result

    def compress_file(self, path: str, *, out: Optional[str] = None, level: str = "balanced") -> bytes:
        fmt = os.path.splitext(path)[1].lstrip(".").lower()
        if fmt == "jpg":
            fmt = "jpeg"
        with open(path, "rb") as f:
            data = f.read()
        job = self.compress(data, fmt, level=level, filename=os.path.basename(path))
        result = self.download(job.download_url) if job.download_url else b""
        if out:
            with open(out, "wb") as f:
                f.write(result)
        return result
