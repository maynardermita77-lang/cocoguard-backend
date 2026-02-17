"""Re-check scan images 21-27 with the UPDATED prediction service (min_agreement=2).
   Reads the predict() result correctly (predictions list, not best_match).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.prediction_service import get_prediction_service

UPLOADS = os.path.join(os.path.dirname(__file__), "uploads", "scans")

# Map scan IDs to filenames + original DB result
scans = {
    21: ("scan_20260217_164033_07dd16b0.jpg", "OUT_OF_SCOPE (0%)"),
    22: ("scan_20260217_164117_9f3f6ca1.jpg", "APW Larvae (69.56%, TTA 4/5)"),
    23: ("scan_20260217_165610_944e5dfa.jpg", "OUT_OF_SCOPE (0%)"),
    24: ("scan_20260217_165843_cc05d691.jpg", "APW Larvae (69.56%, TTA 4/5)"),
    25: ("scan_20260217_165956_54c12e7c.jpg", "OUT_OF_SCOPE (0%)"),
    26: ("scan_20260217_170034_7a4c0ba9.jpg", "OUT_OF_SCOPE (0%)"),
    27: ("scan_20260217_170119_2415cd89.jpg", "OUT_OF_SCOPE (0%)"),
}

svc = get_prediction_service()
if not svc.model_loaded:
    print("ERROR: Model not loaded!")
    sys.exit(1)

# Apply thresholds from router (prediction.py)
DETECTED_THRESHOLD = 60.0
UNCERTAIN_THRESHOLD = 45.0

print("=" * 90)
print(f"{'ID':>3} | {'Original DB Result':<35} | {'New Result (minAgreement=2)':<35} | Match?")
print("=" * 90)

for scan_id, (fname, original) in sorted(scans.items()):
    path = os.path.join(UPLOADS, fname)
    if not os.path.exists(path):
        print(f"{scan_id:>3} | {original:<35} | FILE NOT FOUND")
        continue

    result = svc.predict_from_path(path, confidence_threshold=0.55)
    preds = result.get('predictions', [])

    if preds:
        best = preds[0]
        conf = best['confidence']
        pest = best['pest_type']
        tta = f"TTA {best.get('tta_agreement','?')}/{best.get('tta_total','?')}"

        if conf >= DETECTED_THRESHOLD:
            new_result = f"DETECTED: {pest} ({conf:.1f}%, {tta})"
        elif conf >= UNCERTAIN_THRESHOLD:
            new_result = f"UNCERTAIN: {pest} ({conf:.1f}%, {tta})"
        else:
            new_result = f"OUT_OF_SCOPE ({conf:.1f}%)"
    else:
        new_result = "OUT_OF_SCOPE (0%)"

    # Simple match check
    orig_is_oos = "OUT_OF_SCOPE" in original
    new_is_oos = "OUT_OF_SCOPE" in new_result
    orig_pest = original.split("(")[0].strip() if not orig_is_oos else "OOS"
    new_pest = new_result.split(":")[1].split("(")[0].strip() if ":" in new_result else "OOS"

    if orig_is_oos == new_is_oos:
        match = "YES" if orig_is_oos else ("YES" if orig_pest == new_pest else "DIFF")
    else:
        match = "CHANGED"

    print(f"{scan_id:>3} | {original:<35} | {new_result:<35} | {match}")

print("=" * 90)
print("\nLegend: YES=same result, CHANGED=status changed, DIFF=different pest")
