"""Re-check scan images 21-27 with DEBUG output for predictions."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

from app.services.prediction_service import get_prediction_service

UPLOADS = os.path.join(os.path.dirname(__file__), "uploads", "scans")

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
DETECTED_THRESHOLD = 60.0
UNCERTAIN_THRESHOLD = 45.0

# Suppress verbose model output
import builtins
_real_print = builtins.print
suppress = True

def quiet_print(*args, **kwargs):
    if suppress:
        text = ' '.join(str(a) for a in args)
        if text.startswith("SCAN") or text.startswith("===") or text.startswith("RESULT"):
            _real_print(*args, **kwargs)
    else:
        _real_print(*args, **kwargs)

builtins.print = quiet_print

_real_print("=" * 94)
_real_print(f"{'ID':>3} | {'Original DB Result':<35} | {'New Result (min_agree=2)':<35} | Match?")
_real_print("-" * 94)

for scan_id, (fname, original) in sorted(scans.items()):
    path = os.path.join(UPLOADS, fname)
    if not os.path.exists(path):
        _real_print(f"{scan_id:>3} | {original:<35} | FILE NOT FOUND")
        continue

    result = svc.predict_from_path(path, confidence_threshold=0.55)
    preds = result.get('predictions', [])
    success = result.get('success', False)

    if preds:
        best = preds[0]
        conf = best['confidence']
        pest = best['pest_type']
        tta_agree = best.get('tta_agreement', '?')
        tta_total = best.get('tta_total', '?')

        if conf >= DETECTED_THRESHOLD:
            status = "DETECTED"
        elif conf >= UNCERTAIN_THRESHOLD:
            status = "UNCERTAIN"
        else:
            status = "OUT_OF_SCOPE"
        new_result = f"{status}: {pest} ({conf:.1f}%, {tta_agree}/{tta_total})"
    else:
        new_result = "OUT_OF_SCOPE (no detections)"

    orig_oos = "OUT_OF_SCOPE" in original
    new_oos = "OUT_OF_SCOPE" in new_result
    match = "YES" if orig_oos == new_oos else "CHANGED"

    _real_print(f"{scan_id:>3} | {original:<35} | {new_result:<35} | {match}")

_real_print("=" * 94)
builtins.print = _real_print
