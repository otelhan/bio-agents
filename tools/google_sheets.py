"""
Converts a Google Sheets edit URL to a direct CSV export URL.
The existing CSV loaders in farmer_analytics.py work unchanged with this URL.
"""
import re


def sheets_url_to_csv(url: str) -> str:
    """
    Accepts any Google Sheets URL format and returns a CSV export URL.
    Returns the original URL unchanged if it's not a Google Sheets URL
    (e.g. a raw GitHub CSV URL).
    """
    if "docs.google.com/spreadsheets" not in url:
        return url

    match = re.search(r"/spreadsheets/d/([^/]+)", url)
    if not match:
        return url

    sheet_id = match.group(1)
    gid_match = re.search(r"[#&?]gid=(\d+)", url)
    gid_param = f"&gid={gid_match.group(1)}" if gid_match else ""

    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv{gid_param}"
