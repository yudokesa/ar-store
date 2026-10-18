# AR 3D Store Pipeline

An automated pipeline that converts 3D model files into AR-ready product bundles with a web-based viewer, preview images, QR codes, and e-commerce listing details.

## Project Structure

```
3d-agentic-store/
├── index.html              # Root AR product viewer (Google model-viewer)
├── ar_processor.py         # Main processing script
├── assets/                 # Output: processed AR product bundles
│   └── <product_name>/
│       ├── <product_name>_scaled.glb    # AR-ready GLB (Android / WebXR)
│       ├── <product_name>.usdz          # AR-ready USDZ (iOS Quick Look)
│       ├── ar_qr_code.png               # QR code linking to the AR viewer
│       ├── listing_details.txt          # E-commerce listing copy
│       └── images/
│           └── preview_isometric.png    # Rendered product preview
├── staging_input/          # Input: drop raw 3D files here (.glb, .stl, .obj, .3mf)
└── models/                 # Archived / backup product bundles
```

## Pipeline Overview

1. **Input** — Place raw 3D model files (`.glb`, `.stl`, `.obj`, `.3mf`) into `staging_input/<product_folder>/`.
2. **Process** — Run `ar_processor.py`. It automatically:
   - Loads each 3D mesh and normalizes units to meters (1:1 real-world scale for AR).
   - Exports an AR-scaled `.glb` for Android / WebXR.
   - Exports an AR-scaled `.usdz` for iOS Quick Look.
   - Generates a QR code image that links to the AR viewer URL.
   - Renders an isometric preview PNG.
   - Writes a `listing_details.txt` with title, dimensions, AR link, and marketing copy.
3. **Output** — Everything saves into `assets/<product_name>/`.
4. **View** — Open `index.html?model=<product_name>` in a browser. Supported devices will launch AR directly via the on-screen button.

## Usage

### Setup

```bash
pip install trimesh qrcode numpy usd-core pillow
```

### Process Models

```bash
python ar_processor.py
```

Place your raw 3D files under `staging_input/` (subfolders are fine — the script scans recursively).

### View a Product in AR

Serve the project root with any static web server, then navigate to:

```
http://localhost:8000/index.html?model=hair_comb_for_3d_printing
```

- On iOS Safari: Tap **View in Your Space (AR)** → launches Quick Look.
- On Android Chrome: Launches Scene Viewer or WebXR.
- On desktop: Shows an interactive 3D preview.

## Key Files

- [index.html](index.html) — AR viewer page powered by `<model-viewer>`; reads `?model=` and `?folder=` URL params (defaults to `assets/`).
- [ar_processor.py](ar_processor.py) — Batch processor (`INPUT_DIR=staging_input`, `OUTPUT_DIR=assets`).
