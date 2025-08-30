import xml.etree.ElementTree as ET
from xml.dom import minidom
import gzip
from datetime import datetime, timedelta
import os

# --- Current Local Time (runner already set to Asia/Kolkata in workflow) ---
now = datetime.now().astimezone()
print("🕒 Current local time (GitHub Runner):", now.strftime("%Y-%m-%d %H:%M:%S %Z%z"))

# Input/Output
input_file = "epg/distrotv.xml"
gzip_file = "epg/distrotv.xml.gz"

# --- Helpers ---
def to_local_str(dt_str):
    """Convert UTC string (YYYYmmddHHMMSS) to local (IST) string with offset"""
    try:
        dt_utc = datetime.strptime(dt_str[:14], "%Y%m%d%H%M%S").astimezone()
        return dt_utc.strftime("%Y%m%d%H%M%S %z")
    except ValueError:
        return dt_str

def to_local_dt(dt_str):
    """Convert UTC string to local datetime"""
    try:
        return datetime.strptime(dt_str[:14], "%Y%m%d%H%M%S").astimezone()
    except ValueError:
        return None

# --- Date range: today 00:00 → tomorrow 23:59:59 local ---
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
tomorrow_end = today_start + timedelta(days=2) - timedelta(seconds=1)

# --- Parse XML ---
tree = ET.parse(input_file)
root = tree.getroot()

# Replace <tv> attributes with generator info + generation timestamp
root.attrib.clear()
gen_time = now.strftime("%Y%m%d%H%M%S %z")
root.set("date", gen_time)
root.set("generator-info-name", "EPG Generator (made by Senvora)")
root.set("generator-info-url", "https://github.com/senvora/epg.git")

# --- Collect and clean programmes ---
programmes = []
for programme in root.findall("programme"):
    start_dt, stop_dt = None, None

    for attr in ("start", "stop"):
        if attr in programme.attrib:
            if attr == "start":
                start_dt = to_local_dt(programme.attrib[attr])
            else:
                stop_dt = to_local_dt(programme.attrib[attr])
            programme.set(attr, to_local_str(programme.attrib[attr]))

    if not start_dt or not stop_dt:
        continue

    if stop_dt < today_start or start_dt > tomorrow_end:
        continue

    # Keep only English <title> and <desc>
    for tag in ("title", "desc"):
        elems = programme.findall(tag)
        for e in elems:
            if e.attrib.get("lang") != "en":
                programme.remove(e)

        elem = programme.find(tag)
        if elem is not None and (elem.text is None or elem.text.strip() == ""):
            programme.remove(elem)

    # Remove all other tags
    for child in list(programme):
        if child.tag not in ("title", "desc"):
            programme.remove(child)

    programmes.append(programme)

# --- Collect and sort channels ---
channels = root.findall("channel")
for elem in channels + root.findall("programme"):
    root.remove(elem)

channels.sort(key=lambda c: (c.find("display-name").text or "").lower())
for c in channels:
    root.append(c)

programmes.sort(key=lambda p: (p.attrib.get("channel", "").lower(), p.attrib.get("start", "")))
for p in programmes:
    root.append(p)

# --- Pretty print XML ---
xml_str = ET.tostring(root, encoding="utf-8")
parsed = minidom.parseString(xml_str)
pretty_xml_as_str = parsed.toprettyxml(indent="  ", encoding="utf-8")
pretty_xml_as_str = b"\n".join(line for line in pretty_xml_as_str.splitlines() if line.strip())

# Save only gzipped XML
with gzip.open(gzip_file, "wb") as f_out:
    f_out.write(pretty_xml_as_str)

print(f"✅ Cleaned + 2-day EPG saved to {gzip_file}")
print("📌 Generation timestamp embedded in <tv>:", gen_time)
