import os
import glob
import trimesh
import qrcode
import numpy as np

INPUT_DIR = "staging_input"
OUTPUT_DIR = "output_products"

def generate_listing_text(product_name, dims_mm):
    """Generates ready-to-copy e-commerce listing details."""
    title = product_name.replace("_", " ").title()
    width_cm = dims_mm[0] / 10.0
    depth_cm = dims_mm[1] / 10.0
    height_cm = dims_mm[2] / 10.0

    description = f"""==================================================
PRODUCT LISTING DETAILS
==================================================
Product Title: {title} - 3D Printed Premium Quality

[Dimensions]
- Width: {width_cm:.1f} cm
- Depth: {depth_cm:.1f} cm
- Height: {height_cm:.1f} cm

[Product Highlights]
- High-precision 3D printed daily essential item.
- Interactive 1:1 Scale AR Preview available via QR Code in product photos.
- Durable, eco-friendly material setup.

[Augmented Reality (AR) Preview Link]
https://yudokesa.github.io/ar-store/?model={product_name}

==================================================
"""
    return description

def render_preview_images(mesh, product_out_dir):
    """Renders off-screen preview images of the 3D mesh."""
    images_dir = os.path.join(product_out_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    try:
        scene = mesh.scene()
        png_iso = scene.save_image(resolution=[800, 800], visible=True)
        iso_path = os.path.join(images_dir, "preview_isometric.png")
        with open(iso_path, "wb") as f:
            f.write(png_iso)
        print(f"[✓] Rendered Isometric Preview: {iso_path}")
    except Exception as e:
        print(f"[!] Off-screen rendering skipped: {e}")

def process_3d_file():
    # Only load 3D mesh formats trimesh can process natively
    supported_exts = ("*.stl", "*.obj", "*.glb", "*.3mf")
    files = []
    
    os.makedirs(INPUT_DIR, exist_ok=True)
    
    for ext in supported_exts:
        files.extend(glob.glob(os.path.join(INPUT_DIR, "**", ext), recursive=True))

    if not files:
        print(f"[!] No supported 3D files found in '{INPUT_DIR}/'.")
        return

    for input_file in files:
        filename = os.path.basename(input_file)
        product_name = os.path.splitext(filename)[0]
        
        print(f"\n[*] Processing file: {filename}")

        product_out_dir = os.path.join(OUTPUT_DIR, product_name)
        os.makedirs(product_out_dir, exist_ok=True)

        try:
            mesh = trimesh.load(input_file, force="mesh")
        except Exception as e:
            print(f"[!] Failed to load {filename}: {e}")
            continue

        if isinstance(mesh, trimesh.Scene):
            geometries = [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
            if geometries:
                mesh = trimesh.util.concatenate(geometries)
            else:
                print("[!] Could not extract geometry from scene.")
                continue

        original_extents = mesh.extents.copy()

        # Convert units to meters (1 unit = 1 meter for WebXR/ARKit)
        if max(original_extents) > 2.0:
            mesh.apply_scale(0.001)
            real_mm = original_extents
        else:
            real_mm = original_extents * 1000.0

        print(f"[*] Target Scale: {real_mm[0]:.1f}mm x {real_mm[1]:.1f}mm x {real_mm[2]:.1f}mm")

        # 1. Export Scaled GLB
        glb_path = os.path.join(product_out_dir, f"{product_name}_scaled.glb")
        try:
            mesh.export(glb_path)
            print(f"[✓] Exported AR GLB: {glb_path}")
        except Exception as e:
            print(f"[!] GLB export failed: {e}")

        # 2. Export Scaled USDZ File directly from the scaled mesh
        usdz_path = os.path.join(product_out_dir, f"{product_name}.usdz")
        try:
            mesh.export(usdz_path)
            print(f"[✓] Exported iOS USDZ: {usdz_path}")
        except Exception as e:
            print(f"[!] USDZ export failed (run `pip install usd-core` if missing): {e}")

        # 3. Export AR QR Code
        placeholder_ar_url = f"https://yudokesa.github.io/ar-store/?model={product_name}"
        qr_img = qrcode.make(placeholder_ar_url)
        qr_path = os.path.join(product_out_dir, "ar_qr_code.png")
        qr_img.save(qr_path)
        print(f"[✓] Exported AR QR Code: {qr_path}")

        # 4. Render Preview Image
        render_preview_images(mesh, product_out_dir)

        # 5. Generate Listing Details
        listing_text = generate_listing_text(product_name, real_mm)
        txt_path = os.path.join(product_out_dir, "listing_details.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(listing_text)
        print(f"[✓] Exported Listing Text: {txt_path}")
        print(f"[SUCCESS] Full product bundle ready in: {product_out_dir}")

if __name__ == "__main__":
    process_3d_file()