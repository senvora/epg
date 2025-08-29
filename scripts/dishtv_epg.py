import xml.etree.ElementTree as ET
from xml.dom import minidom
import gzip
from datetime import datetime, timedelta, timezone

# -----------------------------
# Configuration
# -----------------------------
input_file = "epg/dishtv.xml"   # raw grabbed XML
gzip_file = "epg/dishtv.xml.gz" # final gzipped XML

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))

# -----------------------------
# Helpers
# -----------------------------
def relabel_as_ist(dt_str):
    """Convert YYYYMMDDHHMMSS to YYYYMMDDHHMMSS +0530"""
    try:
        dt = datetime.strptime(dt_str[:14], "%Y%m%d%H%M%S")
        return dt.strftime("%Y%m%d%H%M%S +0530")
    except ValueError:
        return dt_str

def parse_dt_ist(dt_str):
    """Parse YYYYMMDDHHMMSS to datetime in IST"""
    try:
        dt = datetime.strptime(dt_str[:14], "%Y%m%d%H%M%S")
        return dt.replace(tzinfo=IST)
    except ValueError:
        return None

# -----------------------------
# Date range: today + tomorrow IST
# -----------------------------
now = datetime.now(IST)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
tomorrow_end = (today_start + timedelta(days=2)) - timedelta(seconds=1)

# -----------------------------
# Parse XML
# -----------------------------
tree = ET.parse(input_file)
root = tree.getroot()

# Relabel <tv> date attribute
if "date" in root.attrib:
    root.set("date", relabel_as_ist(root.attrib["date"]))

# -----------------------------
# Filter programmes
# -----------------------------
programmes = []
for prog in root.findall("programme"):
    # Relabel start/stop
    for attr in ("start", "stop"):
        if attr in prog.attrib:
            prog.set(attr, relabel_as_ist(prog.attrib[attr]))

    # Parse times
    start_dt = parse_dt_ist(prog.attrib.get("start", ""))
    stop_dt = parse_dt_ist(prog.attrib.get("stop", ""))

    if not start_dt or not stop_dt:
        continue

    # Keep only today + tomorrow
    if stop_dt < today_start or start_dt > tomorrow_end:
        continue

    # Keep only English titles
    titles = prog.findall("title")
    for t in titles:
        if t.attrib.get("lang") != "en":
            prog.remove(t)

    # Keep only English descriptions
    descs = prog.findall("desc")
    for d in descs:
        if d.attrib.get("lang") != "en":
            prog.remove(d)

    # Remove other tags except title/desc
    for child in list(prog):
        if child.tag not in ("title", "desc"):
            prog.remove(child)

    # Remove empty title/desc
    for tag in ("title", "desc"):
        el = prog.find(tag)
        if el is not None and (el.text is None or el.text.strip() == ""):
            prog.remove(el)

    programmes.append(prog)

# -----------------------------
# Collect and sort channels
# -----------------------------
channels = root.findall("channel")
for elem in channels + root.findall("programme"):
    root.remove(elem)

# Sort channels alphabetically
channels.sort(key=lambda c: (c.find("display-name").text.lower() if c.find("display-name") is not None else c.attrib.get("id", "").lower()))

# Attach sorted channels
for c in channels:
    root.append(c)

# Sort programmes by channel then start
programmes.sort(key=lambda p: (p.attrib.get("channel", "").lower(), p.attrib.get("start", "")))
for p in programmes:
    root.append(p)

# -----------------------------
# Pretty print XML
# -----------------------------
xml_str = ET.tostring(root, encoding="utf-8")
pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ", encoding="utf-8")
# Remove blank lines
pretty_xml = b"\n".join(line for line in pretty_xml.splitlines() if line.strip())

# -----------------------------
# Save gzipped XML only
# -----------------------------
with gzip.open(gzip_file, "wb") as f:
    f.write(pretty_xml)

print(f"✅ Cleaned, filtered (today + tomorrow IST) & gzipped EPG saved to {gzip_file}")
