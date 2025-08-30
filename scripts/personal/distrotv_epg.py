import xml.etree.ElementTree as ET
from xml.dom import minidom
import gzip
from datetime import datetime, timedelta, timezone

# Timezones
IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

# Input/Output
input_file = "epg/distrotv.xml"
clean_xml_file = "epg/distrotv.xml"
gzip_file = "epg/distrotv.xml.gz"


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

    if not start_dt or not stop_dt:
        continue

    if stop_dt < today_start or start_dt > tomorrow_end:
        continue

    # Keep only English <title> and <desc>
    for tag in ("title", "desc"):
        elements = programme.findall(tag)
        if len(elements) > 1:
            for el in elements:
                if el.attrib.get("lang") != "en":
                    programme.remove(el)

    # Remove unwanted tags
    for child in list(programme):
        if child.tag not in ("title", "desc"):
            programme.remove(child)

    # Remove empty
    for tag in ("title", "desc"):
        el = programme.find(tag)
        if el is not None and (el.text is None or el.text.strip() == ""):
            programme.remove(el)

    programmes.append(programme)

# --- Collect channels ---
channels = root.findall("channel")

# Remove all old ones
for elem in channels + root.findall("programme"):
    root.remove(elem)

# Sort channels alphabetically
channels.sort(key=lambda c: (c.find("display-name").text or "").lower())
for c in channels:
    root.append(c)

# Sort programmes by channel + start
programmes.sort(key=lambda p: (p.attrib.get("channel", "").lower(), p.attrib.get("start", "")))
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

# Save cleaned XML
with open(clean_xml_file, "wb") as f_out:
    f_out.write(pretty_xml_as_str)

# Save gzipped XML
with gzip.open(gzip_file, "wb") as f_out:
    f_out.write(pretty_xml_as_str)

print(f"✅ Cleaned EPG saved as {clean_xml_file} and {gzip_file}")
