"""Debug: check exact return value from predict_from_path for scan #22"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

# Suppress TF warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

from app.services.prediction_service import get_prediction_service

UPLOADS = os.path.join(os.path.dirname(__file__), "uploads", "scans")
path = os.path.join(UPLOADS, "scan_20260217_164117_9f3f6ca1.jpg")  # Scan #22

svc = get_prediction_service()
result = svc.predict_from_path(path, confidence_threshold=0.55)

print("\n" + "=" * 60)
print("RAW RESULT KEYS:", list(result.keys()))
print("SUCCESS:", result.get('success'))
print("PREDICTIONS COUNT:", len(result.get('predictions', [])))
print("PREDICTIONS:", json.dumps(result.get('predictions', []), indent=2, default=str))
print("=" * 60)
