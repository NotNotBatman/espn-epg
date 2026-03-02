#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
import xml.etree.ElementTree as ET
from xml.dom import minidom
from dateutil import parser as dateparser

TZ = pytz.timezone("America/New_York")
OUTPUT_FILE = "epg.xml"
TOTAL_CHANNELS = 399

def fetch_espn_events():
    events = []
    sports = [
        # Pro Sports
        ("basketball", "nba"),
        ("football", "nfl"),
        ("baseball", "mlb"),
        ("hockey", "nhl"),
        ("soccer", "usa.1"),
        ("soccer", "usa.2"),
        ("soccer", "esp.1"),
        ("soccer", "esp.2"),
        ("soccer", "eng.1"),
        ("soccer", "eng.2"),
        ("soccer", "ger.1"),
        ("soccer", "ita.1"),
        ("soccer", "fra.1"),
        ("soccer", "uefa.champions"),
        ("soccer", "uefa.europa"),
        ("soccer", "concacaf.champions"),
        ("soccer", "fifa.worldq.concacaf"),
        # College Sports
        ("basketball", "mens-college-basketball"),
        ("basketball", "womens-college-basketball"),
        ("football", "college-football"),
        ("baseball", "college-baseball"),
        ("hockey", "mens-college-hockey"),
        ("volleyball", "mens-college-volleyball"),
        ("volleyball", "womens-college-volleyball"),
        ("soccer", "mens-college-soccer"),
        ("soccer", "womens-college-soccer"),
        ("lacrosse", "mens-college-lacrosse"),
        ("lacrosse", "womens-college-lacrosse"),
        ("wrestling", "college-wrestling"),
        ("gymnastics", "mens-gymnastics"),
        ("gymnastics", "womens-gymnastics"),
        ("softball", "college-softball"),
        ("tennis", "college-tennis"),
        ("swimming", "college-swimming"),
        ("track-and-field", "college-track-and-field"),
        # Other Pro/International
        ("tennis", "atp"),
        ("tennis", "wta"),
        ("golf", "pga"),
        ("golf", "lpga"),
        ("mma", "ufc"),
        ("boxing", "boxing"),
        ("rugby", "irb.sevens"),
        ("cricket", "icc-cricket"),
        ("cycling", "cycling"),
        ("motorsports", "f1"),
        ("motorsports", "indycar"),
    ]
    today = datetime.now(TZ).strftime("%Y%m%d")
    for sport, league in sports:
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={today}&limit=100"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
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
                            "category": sport.replace("-", " ").title()
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
                            t = time_str.replace("am", " AM").replace("pm", " PM")
                            start_dt = TZ.localize(datetime.strptime(f"{now.strftime('%Y-%m-%d')} {t}", "%Y-%m-%d %I:%M %p"))
                            events.append({
                                "title": title,
                                "start": start_dt,
                                "stop": start_dt + timedelta(hours=2),
                                "category": category
                            })
                        except:
                            pass
    except Exception as e:
        print(f"  Scrape failed: {e}")
    return events

def deduplicate(events):
    seen, unique = set(), []
    for e in sorted(events, key=lambda x: x["start"]):
        k = (e["title"], e["start"].strftime("%H%M"))
        if k not in seen:
            seen.add(k)
            unique.append(e)
    return unique

def format_xmltv_time(dt):
    return dt.strftime("%Y%m%d%H%M%S %z")

def build_xmltv(events):
    tv = ET.Element("tv", attrib={"generator-info-name": "espn-epg"})

    for i in range(1, TOTAL_CHANNELS + 1):
        ch = ET.SubElement(tv, "channel", id=f"ESPN+ {i}")
        ET.SubElement(ch, "display-name").text = f"ESPN+ {i}"

    for i, e in enumerate(events):
        channel_num = (i % TOTAL_CHANNELS) + 1
        channel_id = f"ESPN+ {channel_num}"
        prog = ET.SubElement(tv, "programme",
                             start=format_xmltv_time(e["start"]),
                             stop=format_xmltv_time(e["stop"]),
                             channel=channel_id)
        ET.SubElement(prog, "title").text = e["title"]
        ET.SubElement(prog, "category").text = e.get("category", "Sports")

    return minidom.parseString(ET.tostring(tv)).toprettyxml(indent="  ", encoding="UTF-8").decode()

if __name__ == "__main__":
    print(f"Generating EPG for {datetime.now(TZ).strftime('%B %d, %Y')}...")
    events = deduplicate(fetch_espn_events() + fetch_scrape_events())
    print(f"Found {len(events)} events, assigning across {TOTAL_CHANNELS} channels")
    xmltv = build_xmltv(events)
    with open(OUTPUT_FILE, "w") as f:
        f.write(xmltv)
    print(f"✓ Done — {OUTPUT_FILE} written")
