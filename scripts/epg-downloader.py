import os
import gzip
import xml.etree.ElementTree as ET
import requests
import io
from datetime import datetime, timedelta, timezone

# --- Timezone definitions ---
IST = timezone(timedelta(hours=5, minutes=30))

# --- Output folder ---
output_dir = "epg"
os.makedirs(output_dir, exist_ok=True)


def beautify_element(element, level=0):
    """Recursively add indentation for memory-efficient XML."""
    indent = "\n" + ("  " * level)
    if len(element):
        if not element.text or not element.text.strip():
            element.text = indent + "  "
        for child in element:
            beautify_element(child, level + 1)
        if not element.tail or not element.tail.strip():
            element.tail = indent
    else:
        if level and (not element.tail or not element.tail.strip()):
            element.tail = indent


def normalize_channels_and_programmes(root, provider):
    """Normalize channel IDs and clean metadata."""
    suffix = ".my" if provider == "astro" else ".in"
    id_map = {}

    # Clean and rename channels
    for channel in root.findall("channel"):
        old_id = channel.attrib.get("id", "")
        display_name_elem = channel.find("display-name")

        if display_name_elem is not None:
            name = (display_name_elem.text or "").strip()
            if name:
                new_id = name.lower().replace(" ", "") + suffix
                id_map[old_id] = new_id
                channel.set("id", new_id)

        # Keep only <display-name>
        for child in list(channel):
            if child.tag != "display-name":
                channel.remove(child)

    # Update programmes
    for prog in root.findall("programme"):
        old_ref = prog.attrib.get("channel", "")
        if old_ref in id_map:
            prog.set("channel", id_map[old_ref])

        # Keep only <title> + <desc>
        for child in list(prog):
            if child.tag not in ("title", "desc"):
                prog.remove(child)

    return id_map


# --- NEW: robust timestamp parser ---
def parse_time(ts: str):
    """
    Parse EPG timestamps:
    - Jio style: 'YYYYMMDDHHMMSS' (assumed UTC)
    - With timezone: 'YYYYMMDDHHMMSS +ZZZZ'
    """
    try:
        if len(ts) == 14:
            return datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        elif len(ts) >= 15:
            return datetime.strptime(ts[:15], "%Y%m%d%H%M%S %z")
        else:
            raise ValueError(f"Unrecognized timestamp: {ts}")
    except Exception as e:
        raise ValueError(f"Failed to parse timestamp '{ts}': {e}")


def convert_and_filter_programmes(root):
    """Convert times to IST and filter programmes to only today + tomorrow (IST)."""
    now = datetime.now(IST)
    start_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_day = (start_day + timedelta(days=2))  # exclusive (till 00:00 day after tomorrow)

    keep_progs = []
    for prog in root.findall("programme"):
        try:
            start = parse_time(prog.attrib["start"]).astimezone(IST)
            stop = parse_time(prog.attrib["stop"]).astimezone(IST)

            # Convert attrs to IST
            prog.attrib["start"] = start.strftime("%Y%m%d%H%M%S %z")
            prog.attrib["stop"] = stop.strftime("%Y%m%d%H%M%S %z")

            # Keep if any overlap with [today, tomorrow]
            if stop > start_day and start < end_day:
                keep_progs.append(prog)
        except Exception as e:
            print("⚠️ Time parse failed:", prog.attrib.get("start"), e)
            continue

    # Remove old programmes and re-attach kept ones
    for prog in list(root.findall("programme")):
        root.remove(prog)
    for prog in keep_progs:
        root.append(prog)

    # Also fix <tv date>
    root.set("date", now.strftime("%Y%m%d%H%M%S %z"))


def sort_elements(root):
    """Sort <channel> alphabetically, <programme> by channel + start."""
    channels = sorted(root.findall("channel"), key=lambda c: c.attrib.get("id", ""))

    def prog_sort_key(p):
        return (p.attrib.get("channel", ""), p.attrib.get("start", ""))

    programmes = sorted(root.findall("programme"), key=prog_sort_key)

    # Clear and re-append in sorted order
    for child in list(root):
        root.remove(child)
    for ch in channels:
        root.append(ch)
    for pr in programmes:
        root.append(pr)


def process_and_save(input_url, output_file, provider):
    """Download XML/XML.GZ, normalize, convert times, filter, sort, beautify, and save as .xml.gz only."""
    try:
        print(f"Downloading: {input_url}")
        response = requests.get(input_url, stream=True, timeout=60)
        response.raise_for_status()

        # Detect gzipped content
        content_stream = io.BytesIO(response.content)
        is_gzipped = response.content[:2] == b'\x1f\x8b'

        if is_gzipped:
            xml_stream = gzip.open(content_stream, "rt", encoding="utf-8")
        else:
            xml_stream = io.StringIO(response.text)

        # Parse full XML
        tree = ET.parse(xml_stream)
        root = tree.getroot()

        # Normalize channels/programmes
        normalize_channels_and_programmes(root, provider)

        # Convert times & filter to today + tomorrow IST
        convert_and_filter_programmes(root)

        # Sort & Beautify
        sort_elements(root)
        beautify_element(root)

        # Save gzipped XML only
        gz_path = os.path.join(output_dir, output_file)
        with gzip.open(gz_path, "wt", encoding="utf-8") as gz_out:
            gz_out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            gz_out.write(ET.tostring(root, encoding="unicode"))

        print(f"✅ Saved: {gz_path}")

    except Exception as e:
        print(f"❌ Error processing {input_url}: {e}")


if __name__ == "__main__":
    all_jobs = [
        ("https://www.tsepg.cf/jio.xml.gz", "jiotv.xml.gz", "jiotv"),
    ]

    for url, filename, provider in all_jobs:
        process_and_save(url, filename, provider)
