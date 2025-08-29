import xml.etree.ElementTree as ET
from xml.dom import minidom
import gzip
from datetime import datetime, timedelta, timezone

input_file = "epg/dishtv.xml"
gzip_file = "epg/dishtv.xml.gz"

IST = timezone(timedelta(hours=5, minutes=30))

# --- Helper: relabel as +0530 (IST) ---
def relabel_as_ist(dt_str):
    try:
        dt = datetime.strptime(dt_str[:14], "%Y%m%d%H%M%S")
        return dt.strftime("%Y%m%d%H%M%S +0530")
    except ValueError:
        return dt_str

# --- Helper: parse string to datetime in IST ---
def parse_dt_ist(dt_str):
    try:
        dt = datetime.strptime(dt_str[:14], "%Y%m%d%H%M%S")
        return dt.replace(tzinfo=IST)
    except ValueError:
        return None

# --- Get IST today and tomorrow range ---
now = datetime.now(IST)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
tomorrow_end = (today_start + timedelta(days=2)) - timedelta(seconds=1)

# --- Parse XML ---
tree = ET.parse(input_file)
root = tree.getroot()

# Convert <tv> date (relabel only)
if "date" in root.attrib:
    root.set("date", relabel_as_ist(root.attrib["date"]))

# --- Collect and clean programmes ---
programmes = []
for programme in root.findall("programme"):
    # Relabel start/stop attributes to +0530
    for attr in ("start", "stop"):
        if attr in programme.attrib:
            programme.set(attr, relabel_as_ist(programme.attrib[attr]))

    # Convert start/stop to datetime for filtering
    start_dt = parse_dt_ist(programme.attrib.get("start", ""))
    stop_dt = parse_dt_ist(programme.attrib.get("stop", ""))

    # Skip programme if no valid time
    if not start_dt or not stop_dt:
        continue

    # Keep only if overlaps today/tomorrow
    if stop_dt < today_start or start_dt > tomorrow_end:
        continue

    # Keep only English titles
    titles = programme.findall("title")
    if len(titles) > 1:
        for t in titles:
            if t.attrib.get("lang") != "en":
                programme.remove(t)

    # Keep only English descriptions
    descs = programme.findall("desc")
    if len(descs) > 1:
        for d in descs:
            if d.attrib.get("lang") != "en":
                programme.remove(d)

    # Remove other tags (like <icon>, <url>)
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

# --- Remove existing channels and programmes ---
for elem in channels + root.findall("programme"):
    root.remove(elem)

# --- Sort channels alphabetically ---
def channel_key(c):
    name_elem = c.find("display-name")
    if name_elem is not None and name_elem.text:
        return name_elem.text.lower()
    return c.attrib.get("id", "").lower()

channels.sort(key=channel_key)

# --- Re-attach sorted channels ---
for c in channels:
    root.append(c)

# --- Sort programmes by channel then start ---
def sort_key(p):
    channel = p.attrib.get("channel", "").lower()
    start = p.attrib.get("start", "")
    return (channel, start)

programmes.sort(key=sort_key)

# --- Re-attach sorted programmes ---
for p in programmes:
    root.append(p)

# --- Pretty print XML with indentation ---
xml_str = ET.tostring(root, encoding="utf-8")
parsed = minidom.parseString(xml_str)
pretty_xml_as_str = parsed.toprettyxml(indent="  ", encoding="utf-8")

# Remove blank lines
pretty_xml_as_str = b"\n".join(
    line for line in pretty_xml_as_str.splitlines() if line.strip()
)

# --- Save ONLY gzipped version ---
with gzip.open(gzip_file, "wb") as f_out:
    f_out.write(pretty_xml_as_str)

print(f"✅ Cleaned, filtered (today + tomorrow IST) & gzipped EPG saved to {gzip_file}")
