#!/usr/bin/env python3
"""
Construit data/attacks.json a partir du fichier Excel des attaques de DAB en Suisse.

Strategie de geolocalisation (par ordre de priorite) :
  1. exact   -> colonne GEOLOC (coordonnees GPS fournies)
  2. npa     -> meme code postal qu'une attaque deja geolocalisee
  3. name    -> meme commune (WHERE) qu'une attaque deja geolocalisee
  4. online  -> geocodage Nominatim/OpenStreetMap   (optionnel, requiert reseau)
  5. canton  -> centroide du canton (approximatif, en dernier recours)

Usage :
    python build_data.py                 # sans reseau (etapes 1-3 + 5)
    python build_data.py --geocode       # avec geocodage en ligne (etapes 1-4 + 5)
"""
import json, re, sys, time, argparse
from pathlib import Path
import pandas as pd

SRC = Path(__file__).resolve().parent.parent / "Bancomats__2_.xlsx"
OUT = Path(__file__).resolve().parent.parent / "data" / "attacks.json"

# Centroides approximatifs des 26 cantons (lat, lng)
CANTON = {
    "ZH": (47.41, 8.65), "BE": (46.85, 7.62), "LU": (47.07, 8.10), "UR": (46.77, 8.63),
    "SZ": (47.02, 8.65), "OW": (46.88, 8.25), "NW": (46.96, 8.39), "GL": (47.04, 9.07),
    "ZG": (47.16, 8.52), "FR": (46.68, 7.10), "SO": (47.30, 7.62), "BS": (47.56, 7.59),
    "BL": (47.45, 7.70), "SH": (47.70, 8.62), "AR": (47.38, 9.30), "AI": (47.33, 9.41),
    "SG": (47.23, 9.27), "GR": (46.66, 9.58), "AG": (47.39, 8.20), "TG": (47.57, 9.09),
    "TI": (46.33, 8.80), "VD": (46.57, 6.50), "VS": (46.20, 7.55), "NE": (47.00, 6.83),
    "GE": (46.21, 6.14), "JU": (47.35, 7.16),
}

def clean(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    return s if s and s.lower() != "nan" else None

def parse_geo(v):
    if v is None or pd.isna(v):
        return None
    nums = re.findall(r"-?\d+\.\d+", str(v))
    if len(nums) >= 2:
        lat, lng = float(nums[0]), float(nums[1])
        if 45 < lat < 48 and 5 < lng < 11:   # bounding box Suisse
            return [round(lat, 6), round(lng, 6)]
    return None

def parse_date(row):
    d = row.get("DATE")
    if pd.notna(d):
        try:
            ts = pd.to_datetime(d, errors="coerce")
            if pd.notna(ts) and ts.year > 2000:
                return ts.strftime("%Y-%m-%d")
        except Exception:
            pass
    y = row.get("YEAR")
    if pd.notna(y):
        return f"{int(y)}-01-01"   # date inconnue -> 1er janvier de l'annee
    return None

def parse_time(v):
    if pd.isna(v):
        return None
    s = str(v)
    m = re.search(r"(\d{1,2}):(\d{2})", s)
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None

def best_url(row):
    for c in ("URL_press", "URL_police", "URL_doc", "URL_follow"):
        u = clean(row.get(c))
        if u:
            return u.split(",")[0].strip()
    return None

def geocode_online(npa, town, canton):
    import urllib.request, urllib.parse
    q = ", ".join(p for p in [town, npa, "Switzerland"] if p)
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": 1, "countrycodes": "ch"})
    req = urllib.request.Request(url, headers={"User-Agent": "ch-dab-map/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        if data:
            return [round(float(data[0]["lat"]), 6), round(float(data[0]["lon"]), 6)]
    except Exception as e:
        print("  geocode KO:", q, e, file=sys.stderr)
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geocode", action="store_true", help="active le geocodage en ligne")
    args = ap.parse_args()

    df = pd.read_excel(SRC, sheet_name="DATA_FULL")
    df["geo"] = df["GEOLOC"].apply(parse_geo)

    # Lookups bati a partir des lignes deja geolocalisees
    npa_lu, name_lu = {}, {}
    for _, r in df[df["geo"].notna()].iterrows():
        if pd.notna(r["NPA"]):
            npa_lu.setdefault(int(r["NPA"]), r["geo"])
        if pd.notna(r["WHERE"]):
            name_lu.setdefault(str(r["WHERE"]).strip().lower(), r["geo"])

    records, counts = [], {"exact": 0, "npa": 0, "name": 0, "online": 0, "canton": 0, "none": 0}
    for _, r in df.iterrows
