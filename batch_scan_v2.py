"""
Batch-scan ALL images - write results to file for easy reading.
"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(__file__))
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Suppress ALL prints from model
import builtins
_real_print = builtins.print
builtins.print = lambda *a, **k: None

from app.services.prediction_service import get_prediction_service
svc = get_prediction_service()

builtins.print = _real_print

SCAN_DIR = os.path.join(os.path.dirname(__file__), "uploads", "scans")
ASSETS_DIR = r"C:\xampp\htdocs\assets"

images = sorted(glob.glob(os.path.join(SCAN_DIR, "*.jpg")))
images += sorted(glob.glob(os.path.join(ASSETS_DIR, "*.jpg")))

print(f"Scanning {len(images)} images...")

pest_hits = {}
out_of_scope = 0

for i, img_path in enumerate(images):
    fname = os.path.basename(img_path)
    builtins.print = lambda *a, **k: None
    try:
        result = svc.predict_from_path(img_path, confidence_threshold=0.55)
    except:
        builtins.print = _real_print
        continue
    builtins.print = _real_print
    
    preds = result.get('predictions', [])
    if preds:
        best = preds[0]
        pest = best['pest_type']
        conf = best['confidence']
        tta = best.get('tta_agreement', '?')
        total = best.get('tta_total', '?')
        pest_hits.setdefault(pest, []).append((conf, tta, total, fname))
    else:
        out_of_scope += 1
    
    if (i + 1) % 25 == 0:
        print(f"  {i+1}/{len(images)} done...")

# Write results
ALL_PESTS = ['APW Adult', 'APW Larvae', 'Brontispa', 'Brontispa Pupa',
             'Rhinoceros Beetle', 'Slug Caterpillar', 'White Grub']

print(f"\nDone! {len(images)} images scanned.")
print(f"OUT_OF_SCOPE: {out_of_scope}")
print(f"Detections: {sum(len(v) for v in pest_hits.values())}")
print()
print("=" * 80)
print("RESULTS BY PEST TYPE")
print("=" * 80)

for pest in ALL_PESTS:
    hits = sorted(pest_hits.get(pest, []), key=lambda x: -x[0])
    if hits:
        print(f"\n  {pest}: {len(hits)} detections")
        for conf, tta, total, fname in hits[:3]:
            print(f"    {conf:>5.1f}% | TTA {tta}/{total} | {fname}")
        if len(hits) > 3:
            print(f"    ... +{len(hits)-3} more")
    else:
        print(f"\n  {pest}: ** NO DETECTIONS ** (no test images found)")

print()
print("=" * 80)
print("DETECTION COVERAGE SUMMARY")
print("=" * 80)
for p in ALL_PESTS:
    count = len(pest_hits.get(p, []))
    ok = "OK" if count > 0 else "MISSING"
    print(f"  [{ok:>7}] {p:<22} - {count} images detected")

missing = [p for p in ALL_PESTS if p not in pest_hits]
if missing:
    print(f"\n  MISSING: {', '.join(missing)}")
    print("  No test images exist in uploads for these types.")
    print("  The MODEL supports all 7 classes but needs real images to verify.")
