import gzip
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional, Tuple


def _decode_bytes(data: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="ignore")


def _select_xml_from_zip(data: bytes) -> Optional[bytes]:
    bio = io.BytesIO(data)
    try:
        with zipfile.ZipFile(bio) as z:
            names = z.namelist()
            if not names:
                return None
            pick = None
            for n in names:
                if n.lower().endswith(".xml"):
                    pick = n
                    break
            pick = pick or names[0]
            try:
                return z.read(pick)
            except Exception:
                return None
    except zipfile.BadZipFile:
        return None


def _maybe_gunzip(data: bytes) -> Optional[bytes]:
    if len(data) < 2 or data[0] != 0x1F or data[1] != 0x8B:
        return None
    try:
        return gzip.decompress(data)
    except Exception:
        return None


def _extract_xml_bytes(data: bytes) -> bytes:
    z = _select_xml_from_zip(data)
    if z:
        return z
    g = _maybe_gunzip(data)
    if g:
        z = _select_xml_from_zip(g)
        if z:
            return z
        return g
    return data


def _find_first(channels, predicate) -> Optional[int]:
    for pos, name, typ in channels:
        if predicate(pos, name, typ):
            return pos
    return None


def _sanitize_key(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()
    return cleaned or "fixture"


def parse_ssl2_fixture(data: bytes, filename: str = "") -> Tuple[str, dict]:
    """
    Parse a Sunlite Suite 2 (.ssl2) fixture definition and return (profile_key, profile_dict).
    Best-effort: derives channel count and pan/tilt coarse/fine mapping.
    """
    xml_bytes = _extract_xml_bytes(data)
    xml_text = _decode_bytes(xml_bytes)

    # tolerate headers/junk before XML
    if "<" in xml_text:
        xml_text = xml_text[xml_text.find("<") :]

    root = ET.fromstring(xml_text)

    fixture_name = (
        root.get("Name")
        or root.get("name")
        or (root.findtext(".//Name") or root.findtext(".//NAME"))
        or filename
        or "fixture"
    )

    channels = []
    for idx, ch in enumerate(root.findall(".//Channel"), start=1):
        name = (ch.get("Name") or ch.get("name") or ch.get("Title") or "").strip()
        typ = (ch.get("Type") or ch.get("type") or "").strip()
        pos_fields = [
            ch.get("Address"),
            ch.get("Offset"),
            ch.get("Channel"),
            ch.get("Number"),
            ch.get("Index"),
            ch.get("No"),
        ]
        pos = None
        for pf in pos_fields:
            if pf is None:
                continue
            try:
                pos = int(pf)
                break
            except Exception:
                continue
        if pos is None or pos <= 0:
            pos = idx
        channels.append((pos, name, typ))

    if not channels:
        raise ValueError("No channels found in SSL2")

    channels.sort(key=lambda x: x[0])
    channel_count = max(c[0] for c in channels)

    def is_pan(pos, name, typ):
        n = name.lower()
        t = typ.lower()
        return ("pan" in n or "pan" in t) and "fine" not in n and "fine" not in t

    def is_pan_fine(pos, name, typ):
        n = name.lower()
        t = typ.lower()
        return ("pan" in n or "pan" in t) and ("fine" in n or "fine" in t)

    def is_tilt(pos, name, typ):
        n = name.lower()
        t = typ.lower()
        return ("tilt" in n or "tilt" in t) and "fine" not in n and "fine" not in t

    def is_tilt_fine(pos, name, typ):
        n = name.lower()
        t = typ.lower()
        return ("tilt" in n or "tilt" in t) and ("fine" in n or "fine" in t)

    pan_coarse = _find_first(channels, is_pan)
    pan_fine = _find_first(channels, is_pan_fine) or ((pan_coarse + 1) if pan_coarse else None)
    tilt_coarse = _find_first(channels, is_tilt)
    tilt_fine = _find_first(channels, is_tilt_fine) or ((tilt_coarse + 1) if tilt_coarse else None)

    profile_key = _sanitize_key(fixture_name)
    profile = {
        "v": 1,
        "name": fixture_name,
        "channels": channel_count,
        "source": "ssl2",
    }
    if pan_coarse:
        profile["pan_coarse"] = pan_coarse
    if pan_fine:
        profile["pan_fine"] = pan_fine
    if tilt_coarse:
        profile["tilt_coarse"] = tilt_coarse
    if tilt_fine:
        profile["tilt_fine"] = tilt_fine

    return profile_key, profile
