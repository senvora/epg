import xml.etree.ElementTree as ET
import gzip
from datetime import datetime, timedelta, timezone
import os

IST = timezone(timedelta(hours=5, minutes=30))

input_file = "temp_epg/tempest_config/epg/epg.xml"
gzip_file = "epg/epg.xml.gz"

now = datetime.now(IST)
today = now.date()
tomorrow = today + timedelta(days=1)
end_day = tomorrow  # keep today + tomorrow

def parse_time(timestr: str):
    try:
        dt = datetime.strptime(timestr[:14], "%Y%m%d%H%M%S")
        if " " in timestr:
            offset_str = timestr.split(" ")[1]
            sign = 1 if offset_str[0] == '+' else -1
            hh = int(offset_str[1:3]); mm = int(offset_str[3:5])
            offset = timezone(sign * timedelta(hours=hh, minutes=mm))
            dt = dt.replace(tzinfo=offset)
        else:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST)
    except Exception:
        return None

def indent(elem, level=0):
    """Pretty-print XML with indentation, no blank lines."""
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent(child, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

tree = ET.parse(input_file)
root = tree.getroot()

for programme in list(root.findall("programme")):
    start_dt = parse_time(programme.attrib.get("start", ""))
    if start_dt is None or not (today <= start_dt.date() <= end_day):
        root.remove(programme)
        continue

    for child in list(programme):
        if child.tag not in ("title", "desc"):
            programme.remove(child)

# Apply indentation before writing
indent(root)

os.makedirs(os.path.dirname(gzip_file), exist_ok=True)
with gzip.open(gzip_file, "wb") as f_out:
    tree.write(f_out, encoding="utf-8", xml_declaration=True)

print(f"✅ EPG saved to {gzip_file} (IST today & tomorrow only, no blank lines)")
