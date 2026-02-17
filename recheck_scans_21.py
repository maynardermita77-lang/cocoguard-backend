"""Re-check scan images 21-27 with the UPDATED prediction service (min_agreement=2)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.prediction_service import get_prediction_service
from PIL import Image

UPLOADS = os.path.join(os.path.dirname(__file__), "uploads", "scans")

# Map scan IDs to filenames
scans = {
    21: "scan_20260217_164033_07dd16b0.jpg",
    22: "scan_20260217_164117_9f3f6ca1.jpg",
    23: "scan_20260217_165610_944e5dfa.jpg",
    24: "scan_20260217_165843_cc05d691.jpg",
    25: "scan_20260217_165956_54c12e7c.jpg",
    26: "scan_20260217_170034_7a4c0ba9.jpg",
    27: "scan_20260217_170119_2415cd89.jpg",
}

svc = get_prediction_service()
if not svc.model_loaded:
    print("ERROR: Model not loaded!")
    sys.exit(1)

print(f"Model loaded: {svc.model_path}")
print(f"Labels: {svc.labels}")
print("=" * 80)

for scan_id, fname in sorted(scans.items()):
    path = os.path.join(UPLOADS, fname)
    if not os.path.exists(path):
        print(f"\nScan #{scan_id}: FILE NOT FOUND ({fname})")
        continue

    print(f"\n{'='*80}")
    print(f"SCAN #{scan_id}: {fname} ({os.path.getsize(path):,} bytes)")
    print(f"{'='*80}")

    result = svc.predict_from_path(path, confidence_threshold=0.55)

    status = result.get('status', 'UNKNOWN')
    best = result.get('best_match')
    preds = result.get('predictions', [])

    if best:
        print(f"  STATUS: {status}")
        print(f"  BEST: {best['pest_type']} @ {best['confidence']:.1f}%")
        if best.get('tta_agreement'):
            print(f"  TTA Agreement: {best['tta_agreement']}/{best.get('tta_total', '?')}")
        for p in preds:
            print(f"    - {p['pest_type']}: {p['confidence']:.1f}% "
                  f"(anchors={p.get('anchor_count','?')}, "
                  f"TTA={p.get('tta_agreement','?')}/{p.get('tta_total','?')})")
    else:
        print(f"  STATUS: {status}")
        print(f"  No pest detected")
        if result.get('message'):
            print(f"  Message: {result['message']}")

print(f"\n{'='*80}")
print("RECHECK COMPLETE")
