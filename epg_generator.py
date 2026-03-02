#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
import xml.etree.ElementTree as ET
from xml.dom import minidom
from dateutil import parser as dateparser

CHANNEL_ID = "espnplus.us"
CHANNEL_NAME = "ESPN+"
OUTPUT_FILE = "epg.xml"
TZ = pytz.timezone("America/New_York")

def fetch_espn_events():
    events = []
    sports = [
        ("basketball", "mens-college-basketball"),
        ("basketball", "nba"),
        ("baseball", "mlb"),
        ("hockey", "nhl"),
        ("soccer", "esp.1"),
        ("soccer", "uefa.champions"),
        ("football", "college-football"),
    ]
    today = datetime.now(TZ).strftime("%Y%m%d")
    for sport, league in sports:
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={today}&limit=100"
            data = requests.get(url, timeout=10).json()
            for event in data.get("events", []):
                for comp in event.get("competitions", []):
                    broadcasts = comp.get("broadcasts", [])
                    names = [b.get("names", [""])[0].lower() for b in broadcasts]
                    if any("espn+" in n or "espnplus" in n for n in names) or not broadcasts:
                        start_dt = dateparser.parse(event["date"]).astimezone(TZ)
                        events.append({
                            "title": event.get("name", "ESPN+ Event"),
                            "start": start_dt,
                            "stop": start_dt + timedelta(hours=2),
                            "category": sport.title()
                        })
        except Exception as e:
            print(f"  Skipped {sport}/{league}: {e}")
    return events

def fetch_scrape_events():
    events = []
    now = datetime.now(TZ)
    weekday = now.strftime("%A").lower()
    url = f"https://sportsgamestoday.com/{now.year}-{now.month}-{now.day}-{weekday}-sports.php"
    try:
        soup = BeautifulSoup(requests.get(url, timeout=10).text, "html.parser")
        category = "Sports"
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) == 1:
                    category = cols[0].get_text(strip=True).title()
                elif len(cols) == 3:
                    title, time_str, network = [c.get_text(strip=True) for c in cols]
                    if "ESPN+" in network.upper():
                        try:
                            t = time_str.replace("am"," AM").replace("pm"," PM")
                            start_dt = TZ.localize(datetime.strptime(f"{now.strftime('%Y-%m-%d')} {t}", "%Y-%m-%d %I:%M %p"))
                            events.append({"title": title, "start": start_dt, "stop": start_dt + timedelta(hours=2), "category": category})
                        except: pass
    except Exception as e:
        print(f"  Scrape failed: {e}")
    return events

def build_xmltv(events):
    seen, unique = set(), []
    for e in sorted(events, key=lambda x: x["start"]):
        k = (e["title"], e["start"].strftime("%H%M"))
        if k not in seen:
            seen.add(k)
            unique.append(e)

    tv = ET.Element("tv", attrib={"generator-info-name": "espn-epg"})
    ch = ET.SubElement(tv, "channel", id=CHANNEL_ID)
    ET.SubElement(ch, "display-name").text = CHANNEL_NAME

    for e in unique:
        fmt = lambda dt: dt.strftime("%Y%m%d%H%M%S %z")
        prog = ET.SubElement(tv, "programme", start=fmt(e["start"]), stop=fmt(e["stop"]), channel=CHANNEL_ID)
        ET.SubElement(prog, "title").text = e["title"]
        ET.SubElement(prog, "category").text = e.get("category", "Sports")

    return minidom.parseString(ET.tostring(tv)).toprettyxml(indent="  ", encoding="UTF-8").decode()

if __name__ == "__main__":
    print(f"Generating EPG for {datetime.now(TZ).strftime('%B %d, %Y')}...")
    events = fetch_espn_events() + fetch_scrape_events()
    xmltv = build_xmltv(events)
    with open(OUTPUT_FILE, "w") as f:
        f.write(xmltv)
    print(f"✓ Done — {OUTPUT_FILE} written")
    print("→ https://notnotbatman.github.io/espn-epg/epg.xml")
