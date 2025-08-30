import xml.etree.ElementTree as ET
from xml.dom import minidom
import gzip
from datetime import datetime, timedelta

# Input/Output
input_file = "epg/distrotv.xml"
gzip_file = "epg/distrotv.xml.gz"

# --- Local time now ---
now = datetime.now()
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
tomorrow_end = today_start + timedelta(days=2) - timedelta(seconds=1)

offset_str = " +0530"  # IST offset

print("🕒 Current local runtime:", now.strftime("%Y-%m-%d %H:%M:%S") + offset_str)

# --- Parse XML ---
tree = ET.parse(input_file)
root = tree.getroot()

# --- Collect programmes ---
programmes = []
for programme in root.findall("programme"):
    start_str = programme.attrib.get("start")
    stop_str = programme.attrib.get("stop")
    if not start_str or not stop_str:
        continue

    try:
        start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
        stop_dt = datetime.strptime(stop_str[:14], "%Y%m%d%H%M%S")
    except ValueError:
        continue

    # Keep only if overlaps with today/tomorrow
    if stop_dt < today_start or start_dt > tomorrow_end:
        continue

    # Update start/stop with offset
    programme.set("start", start_dt.strftime("%Y%m%d%H%M%S") + offset_str)
    programme.set("stop", stop_dt.strftime("%Y%m%d%H%M%S") + offset_str)

    # Keep only English <title> and <desc>
    for tag in ("title", "desc"):
        elements = programme.findall(tag)
        if len(elements) > 1:
            for e in elements:
                if e.attrib.get("lang") != "en":
                    programme.remove(e)

        # Remove empty
        element = programme.find(tag)
        if element is not None and (element.text is None or element.text.strip() == ""):
            programme.remove(element)

    # Remove other child tags
    for child in list(programme):
        if child.tag not in ("title", "desc"):
            programme.remove(child)

    programmes.append(programme)

# --- Collect channels ---
channels = root.findall("channel")
for c in channels:
    for url in c.findall("url"):
        c.remove(url)

# Remove everything from root
for elem in channels + root.findall("programme"):
    root.remove(elem)

# Sort channels alphabetically
def channel_key(c):
    name_elem = c.find("display-name")
    return name_elem.text.lower() if name_elem is not None and name_elem.text else c.attrib.get("id", "").lower()

channels.sort(key=channel_key)
for c in channels:
    root.append(c)

# Sort programmes (by channel + start)
programmes.sort(key=lambda p: (p.attrib.get("channel", "").lower(), p.attrib.get("start", "")))
for p in programmes:
    root.append(p)

# --- Set header with offset ---
root.attrib.clear()
root.set("date", now.strftime("%Y%m%d%H%M%S") + offset_str)
root.set("generator-info-name", "EPG Generator (made by Senvora)")
root.set("generator-info-url", "https://github.com/senvora/epg.git")

# --- Pretty print XML ---
xml_str = ET.tostring(root, encoding="utf-8")
parsed = minidom.parseString(xml_str)
pretty_xml_as_str = parsed.toprettyxml(indent="  ", encoding="utf-8")
pretty_xml_as_str = b"\n".join(line for line in pretty_xml_as_str.splitlines() if line.strip())

# Save gzipped XML only
with gzip.open(gzip_file, "wb") as f_out:
    f_out.write(pretty_xml_as_str)

print(f"✅ Cleaned + 2-day EPG saved to {gzip_file}")
