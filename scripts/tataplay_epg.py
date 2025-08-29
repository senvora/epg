import xml.etree.ElementTree as ET
from xml.dom import minidom
import gzip
from datetime import datetime, timedelta, timezone

# Timezones
IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

# Input/Output
input_file = "epg/tataplay.xml"
gzip_file = "epg/tataplay.xml.gz"


# --- Helpers ---
def to_ist_str(dt_str):
    """Convert UTC string to IST string with +0530 offset"""
    try:
        dt_utc = datetime.strptime(dt_str[:14], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        dt_ist = dt_utc.astimezone(IST)
        return dt_ist.strftime("%Y%m%d%H%M%S +0530")
    except ValueError:
        return dt_str


def to_ist_dt(dt_str):
    """Convert UTC string to IST datetime"""
    try:
        dt_utc = datetime.strptime(dt_str[:14], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        return dt_utc.astimezone(IST)
    except ValueError:
        return None


# --- Date range: today 00:00 → tomorrow 23:59:59 IST ---
now = datetime.now(IST)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
tomorrow_end = today_start + timedelta(days=2) - timedelta(seconds=1)


# --- Parse XML ---
tree = ET.parse(input_file)
root = tree.getroot()

# Convert <tv> date if present
if "date" in root.attrib:
    root.set("date", to_ist_str(root.attrib["date"]))

# --- Collect and clean programmes ---
programmes = []
for programme in root.findall("programme"):
    start_dt, stop_dt = None, None

    # Convert start/stop to IST
    for attr in ("start", "stop"):
        if attr in programme.attrib:
            if attr == "start":
                start_dt = to_ist_dt(programme.attrib[attr])
            else:
                stop_dt = to_ist_dt(programme.attrib[attr])
            programme.set(attr, to_ist_str(programme.attrib[attr]))

    # Skip if no valid times
    if not start_dt or not stop_dt:
        continue

    # --- Keep only if overlaps with today/tomorrow ---
    if stop_dt < today_start or start_dt > tomorrow_end:
        continue

    # Keep only English <title>
    titles = programme.findall("title")
    if len(titles) > 1:
        for t in titles:
            if t.attrib.get("lang") != "en":
                programme.remove(t)

    # Keep only English <desc>
    descs = programme.findall("desc")
    if len(descs) > 1:
        for d in descs:
            if d.attrib.get("lang") != "en":
                programme.remove(d)

    # Remove unwanted tags (keep only title + desc)
    for child in list(programme):
        if child.tag not in ("title", "desc"):
            programme.remove(child)

    # Remove empty title/desc
    for tag in ("title", "desc"):
        element = programme.find(tag)
        if element is not None and (element.text is None or element.text.strip() == ""):
            programme.remove(element)

    programmes.append(programme)

# --- Collect channels ---
channels = root.findall("channel")

# Remove old channels + programmes
for elem in channels + root.findall("programme"):
    root.remove(elem)

# Sort channels alphabetically
def channel_key(c):
    name_elem = c.find("display-name")
    if name_elem is not None and name_elem.text:
        return name_elem.text.lower()
    return c.attrib.get("id", "").lower()

channels.sort(key=channel_key)

for c in channels:
    root.append(c)

# Sort programmes (by channel + start)
def programme_key(p):
    channel = p.attrib.get("channel", "").lower()
    start = p.attrib.get("start", "")
    return (channel, start)

programmes.sort(key=programme_key)

for p in programmes:
    root.append(p)

# --- Pretty print XML ---
xml_str = ET.tostring(root, encoding="utf-8")
parsed = minidom.parseString(xml_str)
pretty_xml_as_str = parsed.toprettyxml(indent="  ", encoding="utf-8")

# Remove blank lines
pretty_xml_as_str = b"\n".join(
    line for line in pretty_xml_as_str.splitlines() if line.strip()
)

# Save only gzipped XML
with gzip.open(gzip_file, "wb") as f_out:
    f_out.write(pretty_xml_as_str)

print(f"✅ Cleaned + 2-day EPG saved to {gzip_file}")
