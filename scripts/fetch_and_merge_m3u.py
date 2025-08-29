import requests
import os
import re
from urllib.parse import urlparse

# Read comma-separated URLs from environment variable (injected from GitHub Secrets)
REMOTE_URLS = [u.strip() for u in os.getenv("REMOTE_URLS", "").split(",") if u.strip()]

TARGET_PLAYLIST = "iptv/playlist.m3u"
CHANNELS_FILE = "iptv/channels.txt"


def load_selected_channels():
    """Load list of channel names from channels.txt"""
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def parse_playlist(content):
    """Parse M3U content into dict of {channel_name: [block_lines]}"""
    entries = {}
    lines = [line.strip() for line in content.strip().splitlines() if line.strip()]
    i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF:"):
            name = lines[i].split(",")[-1].strip()
            block = [lines[i]]
            i += 1
            while i < len(lines) and not lines[i].startswith("#EXTINF:"):
                block.append(lines[i])
                i += 1
            entries[name] = block
        else:
            i += 1
    return entries


def fetch_remote_entries(selected_names):
    """Fetch remote M3U files and extract only selected channels"""
    merged_remote = {}
    for url in REMOTE_URLS:
        if not url:
            continue
        domain = urlparse(url).netloc
        print(f"🌐 Fetching from: {domain} (URL hidden)")

        resp = requests.get(url)
        resp.raise_for_status()

        all_entries = parse_playlist(resp.text)
        for name in selected_names:
            if name in all_entries:
                merged_remote[name] = all_entries[name]
    return merged_remote


def read_local_entries():
    """Read existing local playlist (if any)"""
    try:
        with open(TARGET_PLAYLIST, "r", encoding="utf-8") as f:
            return parse_playlist(f.read())
    except FileNotFoundError:
        return {}


def merge_playlists(local, remote):
    """Merge remote entries into local, preserving EXTINF metadata"""
    for name, remote_block in remote.items():
        if name in local:
            local_extinf = local[name][0]  # keep original EXTINF line
            local[name] = [local_extinf] + remote_block[1:]
        else:
            local[name] = remote_block  # add new entry
    return local


def write_merged_playlist(entries):
    """Write merged playlist back to file"""
    with open(TARGET_PLAYLIST, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for i, (_, block) in enumerate(entries.items()):
            f.write("\n".join(block))
            if i < len(entries) - 1:
                f.write("\n\n")
            else:
                f.write("\n")


def main():
    print("🔍 Loading selected channels...")
    selected = load_selected_channels()

    print("🌐 Fetching remote entries...")
    remote_entries = fetch_remote_entries(selected)

    print("📂 Reading local playlist...")
    local_entries = read_local_entries()

    print("🔄 Merging playlists...")
    merged = merge_playlists(local_entries, remote_entries)

    print("💾 Writing merged playlist...")
    write_merged_playlist(merged)
    print("✅ Done.")


if __name__ == "__main__":
    main()
