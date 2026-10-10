from __future__ import annotations
from flask import Blueprint, render_template, request, jsonify, send_from_directory
from pathlib import Path
import sqlite3, json, os, time, math
import random
import requests
import xml.etree.ElementTree as ET

kelowna_bp = Blueprint("kelowna", __name__, template_folder="templates", static_folder="static")
BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
DB_PATH = DATA_DIR / "kelowna_overlay.db"
OSM_PATH = DATA_DIR / "kelowna_downtown.osm"
GEOJSON_PATH = DATA_DIR / "kelowna_blueprint.geojson"
META_PATH = DATA_DIR / "map_source.json"
SNAPSHOT_DIR = DATA_DIR / "streetview_snapshots"

# A manageable first-run downtown Kelowna extract. Change in settings later.
BBOX = (-119.5100, 49.8750, -119.4800, 49.9000)
OSM_URL = "https://api.openstreetmap.org/api/0.6/map?bbox={},{},{},{}".format(*BBOX)

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL,
 kind TEXT NOT NULL DEFAULT 'object',
 lat REAL NOT NULL, lon REAL NOT NULL,
 offset_north_m REAL NOT NULL DEFAULT 0,
 offset_east_m REAL NOT NULL DEFAULT 0,
 description TEXT NOT NULL DEFAULT '',
 action TEXT NOT NULL DEFAULT 'inspect',
 pbx_extension TEXT,
 icon TEXT NOT NULL DEFAULT '◆',
 enabled INTEGER NOT NULL DEFAULT 1,
 world_id TEXT, building_id TEXT, interior_id TEXT,
 layer_name TEXT NOT NULL DEFAULT 'SENTINEL_OBJECTS',
 rotation_deg REAL NOT NULL DEFAULT 0,
 scale REAL NOT NULL DEFAULT 1
);



CREATE TABLE IF NOT EXISTS building_projects(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL,
 address TEXT NOT NULL,
 lat REAL NOT NULL,
 lon REAL NOT NULL,
 width_m REAL NOT NULL DEFAULT 12,
 depth_m REAL NOT NULL DEFAULT 10,
 floors INTEGER NOT NULL DEFAULT 2,
 floor_height_m REAL NOT NULL DEFAULT 3,
 roof_style TEXT NOT NULL DEFAULT 'flat',
 rotation_deg REAL NOT NULL DEFAULT 0,
 footprint_json TEXT NOT NULL DEFAULT '[]',
 notes TEXT NOT NULL DEFAULT '',
 created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS street_annotations(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 title TEXT NOT NULL,
 annotation_type TEXT NOT NULL DEFAULT 'note',
 lat REAL NOT NULL,
 lon REAL NOT NULL,
 pano_id TEXT,
 heading REAL NOT NULL DEFAULT 0,
 pitch REAL NOT NULL DEFAULT 0,
 zoom REAL NOT NULL DEFAULT 1,
 note TEXT NOT NULL DEFAULT '',
 instructions TEXT NOT NULL DEFAULT '',
 action TEXT NOT NULL DEFAULT 'inspect',
 target TEXT,
 layer_name TEXT NOT NULL DEFAULT 'STREET_ANNOTATIONS',
 created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS notes(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 node_id INTEGER,
 title TEXT NOT NULL,
 body TEXT NOT NULL,
 created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS network_nodes(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL,
 node_type TEXT NOT NULL,
 lat REAL,
 lon REAL,
 x_m REAL NOT NULL DEFAULT 0,
 y_m REAL NOT NULL DEFAULT 0,
 layer_name TEXT NOT NULL DEFAULT 'NET_LOGICAL',
 address TEXT,
 pbx_extension TEXT,
 vlan TEXT,
 ssid TEXT,
 notes TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS network_links(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 a_id INTEGER NOT NULL,
 b_id INTEGER NOT NULL,
 link_type TEXT NOT NULL DEFAULT 'ethernet',
 layer_name TEXT NOT NULL DEFAULT 'NET_LOGICAL',
 capacity TEXT,
 label TEXT,
 notes TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS cad_objects(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 object_type TEXT NOT NULL,
 x_m REAL NOT NULL DEFAULT 0,
 y_m REAL NOT NULL DEFAULT 0,
 z_m REAL NOT NULL DEFAULT 0,
 width_m REAL NOT NULL DEFAULT 4,
 depth_m REAL NOT NULL DEFAULT 4,
 height_m REAL NOT NULL DEFAULT 3,
 rotation_deg REAL NOT NULL DEFAULT 0,
 layer_name TEXT NOT NULL DEFAULT 'BUILDINGS',
 label TEXT NOT NULL DEFAULT '',
 payload TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS kiosk_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 kiosk_id TEXT NOT NULL,
 event_type TEXT NOT NULL,
 payload TEXT NOT NULL DEFAULT '{}',
 created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sanctuary_rooms(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 building_project_id INTEGER,
 name TEXT NOT NULL DEFAULT 'Sanctuary Room',
 width_m REAL NOT NULL DEFAULT 7,
 depth_m REAL NOT NULL DEFAULT 6,
 objects_json TEXT NOT NULL DEFAULT '[]',
 routine_json TEXT NOT NULL DEFAULT '{}',
 updated_at INTEGER NOT NULL
);
"""

SEED_NODES = [
    ("Downtown Sentinel Doorway","doorway",49.8879,-119.4960,5,7,
     "Entry into the parallel downtown district.","enter_world","6101","🚪",
     "parallel-downtown","gateway-01","lobby","SENTINEL_DOORS"),
    ("Queensway PBX Terminal","pbx",49.8891,-119.4954,-4,8,
     "Interactive PBX terminal.","pbx","6102","☎",
     "parallel-downtown","terminal-01","terminal-room","PBX_TERMINALS"),
    ("Mission Parallel House","building",49.8550,-119.4890,6,-5,
     "Custom building with an explorable interior.","enter_building","6104","⌂",
     "parallel-mission","mission-house-01","foyer","CUSTOM_BUILDINGS"),
]

def conn():
    c=sqlite3.connect(DB_PATH)
    c.row_factory=sqlite3.Row
    return c

def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with conn() as c:
        c.executescript(SCHEMA)
        if c.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 0:
            c.executemany("""INSERT INTO nodes
              (name,kind,lat,lon,offset_north_m,offset_east_m,description,action,
               pbx_extension,icon,world_id,building_id,interior_id,layer_name)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", SEED_NODES)
        if c.execute("SELECT COUNT(*) FROM network_nodes").fetchone()[0] == 0:
            c.execute("""INSERT INTO network_nodes
              (name,node_type,x_m,y_m,layer_name,address,pbx_extension,vlan,ssid)
              VALUES(?,?,?,?,?,?,?,?,?)""",
              ("Sentinel Core","router",0,0,"NET_LOGICAL","10.10.0.1","6000","10",None))
            c.execute("""INSERT INTO network_nodes
              (name,node_type,x_m,y_m,layer_name,address,pbx_extension,vlan,ssid)
              VALUES(?,?,?,?,?,?,?,?,?)""",
              ("Downtown Kiosk","kiosk",150,70,"PBX_TERMINALS","10.10.10.11","6101","10",None))
            c.execute("""INSERT INTO network_nodes
              (name,node_type,x_m,y_m,layer_name,address,pbx_extension,vlan,ssid)
              VALUES(?,?,?,?,?,?,?,?,?)""",
              ("Sentinel AP","wifi_ap",-120,-80,"WIFI_COVERAGE","10.10.20.2",None,"20","SENTINEL"))
            ids=[r[0] for r in c.execute("SELECT id FROM network_nodes ORDER BY id").fetchall()]
            if len(ids)>=3:
                c.execute("INSERT INTO network_links(a_id,b_id,link_type,layer_name,capacity,label) VALUES(?,?,?,?,?,?)",
                          (ids[0],ids[1],"ethernet","NET_LOGICAL","1G","Core ↔ Kiosk"))
                c.execute("INSERT INTO network_links(a_id,b_id,link_type,layer_name,capacity,label) VALUES(?,?,?,?,?,?)",
                          (ids[0],ids[2],"ethernet","NET_LOGICAL","1G","Core ↔ AP"))

def _tagdict(el):
    return {t.attrib.get("k",""): t.attrib.get("v","") for t in el.findall("tag")}

def osm_to_geojson(osm_file: Path, out_file: Path):
    tree=ET.parse(osm_file)
    root=tree.getroot()
    node_xy={}
    node_tags={}
    for n in root.findall("node"):
        try:
            node_xy[n.attrib["id"]] = (float(n.attrib["lon"]), float(n.attrib["lat"]))
            node_tags[n.attrib["id"]] = _tagdict(n)
        except Exception:
            pass

    features=[]
    for w in root.findall("way"):
        tags=_tagdict(w)
        coords=[node_xy.get(nd.attrib.get("ref")) for nd in w.findall("nd")]
        coords=[c for c in coords if c]
        if len(coords)<2:
            continue

        layer=None
        geom="LineString"
        if "highway" in tags:
            layer="ROADS"
            if tags.get("highway") in {"footway","path","cycleway","steps","pedestrian"}:
                layer="PATHS"
        elif "building" in tags:
            layer="BUILDINGS"; geom="Polygon"
        elif tags.get("natural")=="water" or "waterway" in tags:
            layer="WATER"
        elif "railway" in tags:
            layer="RAIL"
        elif tags.get("landuse") in {"residential","commercial","industrial","retail"}:
            layer="LANDUSE"; geom="Polygon"
        elif "amenity" in tags:
            layer="AMENITIES"
        if not layer:
            continue

        if geom=="Polygon" and coords[0]!=coords[-1]:
            coords.append(coords[0])
        geometry={"type":geom,"coordinates": [coords] if geom=="Polygon" else coords}
        features.append({
            "type":"Feature",
            "geometry":geometry,
            "properties":{
                "osm_id":w.attrib.get("id"),
                "layer":layer,
                "name":tags.get("name",""),
                "highway":tags.get("highway",""),
                "building":tags.get("building",""),
                "amenity":tags.get("amenity",""),
                "landuse":tags.get("landuse",""),
                "source":"OpenStreetMap"
            }
        })

    # useful tagged point features
    for nid, tags in node_tags.items():
        if not tags:
            continue
        layer=None
        if tags.get("highway")=="bus_stop" or tags.get("public_transport"):
            layer="TRANSIT"
        elif "amenity" in tags:
            layer="AMENITIES"
        elif tags.get("highway")=="traffic_signals":
            layer="TRAFFIC"
        if layer and nid in node_xy:
            features.append({
                "type":"Feature",
                "geometry":{"type":"Point","coordinates":node_xy[nid]},
                "properties":{
                    "osm_id":nid,"layer":layer,"name":tags.get("name",""),
                    "amenity":tags.get("amenity",""),"source":"OpenStreetMap"
                }
            })

    fc={"type":"FeatureCollection","features":features}
    out_file.write_text(json.dumps(fc), encoding="utf-8")
    return len(features)

def ensure_map_cache(force=False):
    if GEOJSON_PATH.exists() and not force:
        return {"ok":True,"cached":True,"path":str(GEOJSON_PATH)}
    try:
        r=requests.get(OSM_URL,timeout=45,headers={"User-Agent":"SentinelKelownaBlueprint/3.0"})
        r.raise_for_status()
        OSM_PATH.write_bytes(r.content)
        count=osm_to_geojson(OSM_PATH,GEOJSON_PATH)
        META_PATH.write_text(json.dumps({
            "source":"OpenStreetMap contributors",
            "license":"ODbL 1.0",
            "url":"https://www.openstreetmap.org/",
            "download_url":OSM_URL,
            "bbox":BBOX,
            "downloaded_at":int(time.time()),
            "features":count
        },indent=2),encoding="utf-8")
        return {"ok":True,"cached":False,"features":count}
    except Exception as e:
        # keep app usable even offline; user can retry from UI
        return {"ok":False,"error":str(e)}

def rows(sql,args=()):
    with conn() as c:return [dict(r) for r in c.execute(sql,args).fetchall()]

@kelowna_bp.get("/")
def overlay():
    return render_template("kelowna_overlay.html", kiosk=False,
        google_maps_api_key=os.environ.get("GOOGLE_MAPS_API_KEY","").strip())

@kelowna_bp.get("/kiosk")
def kiosk():
    return render_template("kelowna_overlay.html", kiosk=True,
        google_maps_api_key=os.environ.get("GOOGLE_MAPS_API_KEY","").strip())

@kelowna_bp.get("/api/map")
def get_map():
    if not GEOJSON_PATH.exists():
        status=ensure_map_cache()
        if not status.get("ok"):
            return jsonify(type="FeatureCollection",features=[],download_error=status.get("error"))
    return jsonify(json.loads(GEOJSON_PATH.read_text()))

@kelowna_bp.post("/api/map/refresh")
def refresh_map():
    return jsonify(ensure_map_cache(force=True))

@kelowna_bp.get("/api/map/meta")
def map_meta():
    return jsonify(json.loads(META_PATH.read_text())) if META_PATH.exists() else jsonify({"source":"not downloaded"})

@kelowna_bp.get("/api/open-tour")
def open_tour():
    """Return nearby open Panoramax pictures using a fixed, safe upstream."""
    try:
        west=float(request.args.get("west")); south=float(request.args.get("south"))
        east=float(request.args.get("east")); north=float(request.args.get("north"))
        if not (-180<=west<=180 and -180<=east<=180 and -90<=south<=90 and -90<=north<=90):
            raise ValueError("coordinates out of range")
        r=requests.get("https://api.panoramax.xyz/api/search",params={"bbox":f"{west},{south},{east},{north}","limit":80},timeout=12)
        r.raise_for_status(); pictures=[]
        for feature in r.json().get("features",[]):
            assets=feature.get("assets") or {}; href=None
            for key in ("hd","sd","thumb","visual","thumbnail"):
                asset=assets.get(key)
                if isinstance(asset,dict) and asset.get("href"): href=asset["href"]; break
            coords=(feature.get("geometry") or {}).get("coordinates") or []
            if href and len(coords)>=2:
                pictures.append({"url":href,"lon":coords[0],"lat":coords[1],"id":feature.get("id"),"provider":"Panoramax"})
        return jsonify(ok=True,pictures=pictures,provider="Panoramax federation")
    except Exception as exc:
        return jsonify(ok=False,pictures=[],error=str(exc),fallback="animated-map")

@kelowna_bp.post("/api/streetview/snapshot")
def streetview_snapshot():
    """Save one Google Street View Static API image in the local project."""
    key=os.environ.get("GOOGLE_MAPS_API_KEY","").strip()
    if not key:
        return jsonify(ok=False,error="GOOGLE_MAPS_API_KEY is not configured in .env"),400
    data=request.get_json(silent=True) or {}
    try:
        lat=float(data.get("lat")); lon=float(data.get("lon"))
        heading=float(data.get("heading",0)); pitch=float(data.get("pitch",0)); fov=float(data.get("fov",90))
        if not (-90<=lat<=90 and -180<=lon<=180): raise ValueError("coordinates out of range")
        heading%=360; pitch=max(-90,min(90,pitch)); fov=max(10,min(120,fov))
    except (TypeError,ValueError) as exc:
        return jsonify(ok=False,error=f"Invalid snapshot settings: {exc}"),400
    try:
        response=requests.get("https://maps.googleapis.com/maps/api/streetview",params={
            "size":"640x640","location":f"{lat:.7f},{lon:.7f}","heading":heading,
            "pitch":pitch,"fov":fov,"key":key,"return_error_code":"true"
        },timeout=25)
        response.raise_for_status()
        content_type=response.headers.get("Content-Type","")
        if not content_type.startswith("image/"):
            raise ValueError("Google did not return an image. Check Street View Static API and billing.")
        SNAPSHOT_DIR.mkdir(parents=True,exist_ok=True)
        stamp=time.strftime("%Y%m%d_%H%M%S")
        filename=f"streetview_{stamp}_{lat:.5f}_{lon:.5f}.jpg"
        path=SNAPSHOT_DIR/filename; path.write_bytes(response.content)
        return jsonify(ok=True,filename=filename,url=f"/kelowna/streetview-snapshots/{filename}",lat=lat,lon=lon)
    except Exception as exc:
        return jsonify(ok=False,error=str(exc)),502

@kelowna_bp.get("/streetview-snapshots/<path:filename>")
def saved_streetview_snapshot(filename):
    return send_from_directory(SNAPSHOT_DIR,filename)

@kelowna_bp.get("/api/nodes")
def get_nodes(): return jsonify(rows("SELECT * FROM nodes WHERE enabled=1 ORDER BY id"))

@kelowna_bp.get("/api/network/nodes")
def network_nodes(): return jsonify(rows("SELECT * FROM network_nodes ORDER BY id"))

@kelowna_bp.get("/api/network/links")
def network_links(): return jsonify(rows("SELECT * FROM network_links ORDER BY id"))

@kelowna_bp.post("/api/network/nodes")
def add_network_node():
    d=request.get_json(force=True)
    with conn() as c:
        cur=c.execute("""INSERT INTO network_nodes
          (name,node_type,lat,lon,x_m,y_m,layer_name,address,pbx_extension,vlan,ssid,notes)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
          (d.get("name","Network Node"),d.get("node_type","device"),d.get("lat"),d.get("lon"),
           float(d.get("x_m",0)),float(d.get("y_m",0)),d.get("layer_name","NET_LOGICAL"),
           d.get("address"),d.get("pbx_extension"),d.get("vlan"),d.get("ssid"),
           json.dumps(d.get("notes",{}))))
    return jsonify(ok=True,id=cur.lastrowid)

@kelowna_bp.post("/api/network/links")
def add_network_link():
    d=request.get_json(force=True)
    with conn() as c:
        cur=c.execute("""INSERT INTO network_links
          (a_id,b_id,link_type,layer_name,capacity,label,notes)
          VALUES(?,?,?,?,?,?,?)""",
          (int(d["a_id"]),int(d["b_id"]),d.get("link_type","ethernet"),
           d.get("layer_name","NET_LOGICAL"),d.get("capacity"),d.get("label"),
           json.dumps(d.get("notes",{}))))
    return jsonify(ok=True,id=cur.lastrowid)

@kelowna_bp.post("/api/pbx/call")
def pbx_call():
    d=request.get_json(force=True)
    ext=str(d.get("extension","")).strip()
    if not ext:return jsonify(error="extension required"),400
    return jsonify(ok=True,mode="simulated",message=f"PBX simulation: calling extension {ext}")


@kelowna_bp.get("/api/street-annotations")
def list_street_annotations():
    return jsonify(rows("SELECT * FROM street_annotations ORDER BY created_at DESC, id DESC"))

@kelowna_bp.post("/api/street-annotations")
def add_street_annotation():
    d=request.get_json(force=True)
    if "lat" not in d or "lon" not in d:
        return jsonify(error="lat and lon required"),400
    with conn() as c:
        cur=c.execute("""INSERT INTO street_annotations
          (title,annotation_type,lat,lon,pano_id,heading,pitch,zoom,note,instructions,action,target,layer_name,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (str(d.get("title","Sentinel Pin"))[:120],str(d.get("annotation_type","note"))[:40],
           float(d["lat"]),float(d["lon"]),d.get("pano_id"),float(d.get("heading",0)),
           float(d.get("pitch",0)),float(d.get("zoom",1)),str(d.get("note",""))[:4000],
           str(d.get("instructions",""))[:4000],str(d.get("action","inspect"))[:40],
           str(d.get("target",""))[:240] or None,str(d.get("layer_name","STREET_ANNOTATIONS"))[:80],
           int(time.time())))
    return jsonify(ok=True,id=cur.lastrowid)

@kelowna_bp.delete("/api/street-annotations/<int:annotation_id>")
def delete_street_annotation(annotation_id):
    with conn() as c:
        c.execute("DELETE FROM street_annotations WHERE id=?",(annotation_id,))
    return jsonify(ok=True)


@kelowna_bp.get("/api/building-projects")
def list_building_projects():
    return jsonify(rows("SELECT * FROM building_projects ORDER BY created_at DESC, id DESC"))

@kelowna_bp.post("/api/building-projects")
def add_building_project():
    d=request.get_json(force=True)
    for k in ("address","lat","lon"):
        if k not in d:
            return jsonify(error=f"{k} required"),400
    with conn() as c:
        cur=c.execute("""INSERT INTO building_projects
          (name,address,lat,lon,width_m,depth_m,floors,floor_height_m,roof_style,rotation_deg,footprint_json,notes,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (str(d.get("name","Address Build"))[:120],str(d["address"])[:300],float(d["lat"]),float(d["lon"]),
           float(d.get("width_m",12)),float(d.get("depth_m",10)),int(d.get("floors",2)),
           float(d.get("floor_height_m",3)),str(d.get("roof_style","flat"))[:40],
           float(d.get("rotation_deg",0)),json.dumps(d.get("footprint",[])),
           str(d.get("notes",""))[:4000],int(time.time())))
    return jsonify(ok=True,id=cur.lastrowid)

@kelowna_bp.delete("/api/building-projects/<int:project_id>")
def delete_building_project(project_id):
    with conn() as c:
        c.execute("DELETE FROM building_projects WHERE id=?",(project_id,))
    return jsonify(ok=True)

@kelowna_bp.get("/api/sanctuary/rooms")
def list_sanctuary_rooms():
    return jsonify(rows("SELECT * FROM sanctuary_rooms ORDER BY updated_at DESC, id DESC"))

@kelowna_bp.post("/api/sanctuary/rooms")
def save_sanctuary_room():
    d=request.get_json(force=True)
    room_id=d.get("id")
    values=(d.get("building_project_id") or None,str(d.get("name","Sanctuary Room"))[:120],
            max(3,min(20,float(d.get("width_m",7)))),max(3,min(20,float(d.get("depth_m",6)))),
            json.dumps(d.get("objects",[])),json.dumps(d.get("routine",{})),int(time.time()))
    with conn() as c:
        if room_id:
            c.execute("""UPDATE sanctuary_rooms SET building_project_id=?,name=?,width_m=?,depth_m=?,
                      objects_json=?,routine_json=?,updated_at=? WHERE id=?""",values+(int(room_id),))
            saved_id=int(room_id)
        else:
            cur=c.execute("""INSERT INTO sanctuary_rooms(building_project_id,name,width_m,depth_m,
                          objects_json,routine_json,updated_at) VALUES(?,?,?,?,?,?,?)""",values)
            saved_id=cur.lastrowid
    return jsonify(ok=True,id=saved_id)

@kelowna_bp.get("/api/sanctuary/sensors")
def sanctuary_sensors():
    return jsonify(mode="simulation",timestamp=int(time.time()),
        temperature_c=round(21.5+random.uniform(-.6,.6),1),humidity_pct=round(43+random.uniform(-3,3),1),
        co2_ppm=int(610+random.uniform(-45,45)),voc_index=int(72+random.uniform(-8,8)),
        pm25_ugm3=round(5.4+random.uniform(-1.2,1.2),1),sound_db=round(32+random.uniform(-3,5),1),
        light_lux=int(110+random.uniform(-15,15)),motion=random.random()<.08)
