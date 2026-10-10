# Sentinel Atlas + Ghost Collaboration v1001

This release combines Sentinel Atlas, the Kelowna CAD/GIS tools, and Ghost
Sentinel Hub into one local collaboration package.

## Quick start — Windows

Double-click `start_windows.bat`. Keep both terminal windows open. Atlas opens
at `http://127.0.0.1:5010/` and Ghost Collaboration runs at
`http://127.0.0.1:5011/`.

## Quick start — Kali / Ubuntu

Open a terminal in this folder and run:

```bash
chmod +x start_kali.sh
./start_kali.sh
```

For Ubuntu under Windows WSL, the simplest command is:

```bash
chmod +x start_atlas.sh
./start_atlas.sh
```

The WSL launcher uses Ubuntu's Python and opens Atlas in your Windows browser,
so Python does not need to be installed separately on Windows.

The launcher creates a private Python environment, installs the requirements,
starts both services, and opens Atlas.

## How the two sides collaborate

- Atlas navigation contains a **Ghost Collaboration** button.
- Ghost Hub contains a **Return to Sentinel Atlas** button.
- In Ghost chat, `!atlas` checks the live connection.
- In Ghost chat, `!atlas worlds` lists worlds saved in Atlas.
- Existing Ghost features remain available: lobby chat, presence, direct
  messages, sealed direct messages, PBX directory, and builder commands.
- Existing Atlas features remain available: Living World, world/home/decorator
  forges, city simulation, Kelowna Command Atlas, network planning, building
  designer, Sanctuary designer, and Perpetual Journey simulation.

All saved information remains local in this folder. `worlds.db` stores Atlas
worlds; `data/kelowna_overlay.db` stores Kelowna projects; Ghost state is stored
in JSON files inside `ghost_hub` as it is created.

## Optional map keys

Copy `.env.example` to `.env` and add a Google Maps API key only if you want
Google address lookup or Street View. The application otherwise uses its
offline/cached views and OpenStreetMap support. Panoramax photographs depend on
open coverage in the selected area.

In **Perpetual Journey**, paste a Google Street View URL or latitude/longitude,
press **Use Paste as Destination**, then start the perpetual loop. You can open
the current projected point in Google Street View or save a 640×640 snapshot.
Saved images are kept in `data/streetview_snapshots`. Optional automatic mode
saves once at the destination and once after returning home (not on every loop,
which protects against repeated API charges). Google Cloud must have
Maps JavaScript API and Street View Static API enabled, with billing configured.

The Journey, Guardian, network, Ryoko, and Sanctuary modules are planning and
simulation tools. They do not control physical devices or perform physical
surveillance.

## Troubleshooting

- If a port is already in use, close the earlier Sentinel window and launch
  again.
- If the browser does not open automatically, visit the two local addresses
  above.
- On Linux, `python3-venv` may need to be installed once by your system package
  manager.
