"""
Batch-scan ALL images in uploads/scans + assets/ to discover
which of the 7 pest types the model can detect.
"""
import sys, os, glob, time
sys.path.insert(0, os.path.dirname(__file__))
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

from app.services.prediction_service import get_prediction_service

svc = get_prediction_service()
if not svc.model_loaded:
    print("ERROR: Model not loaded!")
    sys.exit(1)

# Suppress internal prints
import builtins
_real_print = builtins.print
builtins.print = lambda *a, **k: None

SCAN_DIR = os.path.join(os.path.dirname(__file__), "uploads", "scans")
ASSETS_DIR = r"C:\xampp\htdocs\assets"

# Collect all images
images = []
for f in sorted(glob.glob(os.path.join(SCAN_DIR, "*.jpg"))):
    images.append(f)
for f in sorted(glob.glob(os.path.join(ASSETS_DIR, "*.jpg"))):
    images.append(f)

builtins.print = _real_print
print(f"Found {len(images)} images to scan")
print("=" * 90)

# Track per-pest type results
pest_hits = {}  # pest_type -> [(confidence, tta_agreement, filename), ...]
out_of_scope = 0
errors = 0

for i, img_path in enumerate(images):
    fname = os.path.basename(img_path)
    
    # Suppress model output
    builtins.print = lambda *a, **k: None
    try:
        result = svc.predict_from_path(img_path, confidence_threshold=0.55)
    except Exception as e:
        builtins.print = _real_print
        errors += 1
        continue
    builtins.print = _real_print
    
    preds = result.get('predictions', [])
    if preds:
        best = preds[0]
        pest = best['pest_type']
        conf = best['confidence']
        tta = best.get('tta_agreement', '?')
        total = best.get('tta_total', '?')
        
        if pest not in pest_hits:
            pest_hits[pest] = []
        pest_hits[pest].append((conf, tta, total, fname))
    else:
        out_of_scope += 1
    
    # Progress
    if (i + 1) % 20 == 0:
        print(f"  Processed {i+1}/{len(images)}...")

print(f"\nProcessed {len(images)} images. Errors: {errors}")
print(f"OUT_OF_SCOPE (no pest): {out_of_scope}")
print("\n" + "=" * 90)
print("DETECTION RESULTS BY PEST TYPE")
print("=" * 90)

ALL_PESTS = ['APW Adult', 'APW Larvae', 'Brontispa', 'Brontispa Pupa',
             'Rhinoceros Beetle', 'Slug Caterpillar', 'White Grub']

for pest in ALL_PESTS:
    hits = pest_hits.get(pest, [])
    if hits:
        # Sort by confidence descending
        hits.sort(key=lambda x: -x[0])
        print(f"\n{pest}: {len(hits)} detections")
        for conf, tta, total, fname in hits[:5]:  # Show top 5
            print(f"  {conf:>5.1f}% | TTA {tta}/{total} | {fname}")
        if len(hits) > 5:
            print(f"  ... and {len(hits)-5} more")
    else:
        print(f"\n{pest}: *** NO DETECTIONS FOUND ***")

# Summary
print("\n" + "=" * 90)
print("SUMMARY")
print("=" * 90)
detected_types = set(pest_hits.keys())
all_types = set(ALL_PESTS)
missing = all_types - detected_types
extra = detected_types - all_types

print(f"Detected pest types: {len(detected_types)}/7")
for p in ALL_PESTS:
    status = "DETECTED" if p in detected_types else "MISSING"
    count = len(pest_hits.get(p, []))
    print(f"  {'[OK]' if status == 'DETECTED' else '[!!]'} {p:<22} - {count} images")

if missing:
    print(f"\nMISSING TYPES: {', '.join(sorted(missing))}")
    print("  These pest types were not detected in any of the scanned images.")
    print("  This may be because no test images of these pests exist in uploads.")
if extra:
    print(f"\nUNEXPECTED TYPES: {', '.join(sorted(extra))}")
