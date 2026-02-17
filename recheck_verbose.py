import sys, os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
sys.path.insert(0, '.')
from app.services.prediction_service import PestPredictionService
from PIL import Image

svc = PestPredictionService()
svc.load_model()

for img_name in ['scan_20260216_174539_9eeee086.jpg', 'scan_20260216_175000_381b105c.jpg']:
    path = os.path.join('uploads', 'scans', img_name)
    if not os.path.exists(path):
        print(f"{img_name}: NOT FOUND")
        continue
    img = Image.open(path)
    result = svc.predict(img)
    preds = result.get('predictions', [])
    print(f"\n=== {img_name} ===")
    print(f"Total predictions: {len(preds)}")
    for p in preds:
        pest = p.get('pest_type', '?')
        conf = p.get('confidence', 0)
        agree = p.get('tta_agreement', '?')
        total = p.get('tta_total', '?')
        print(f"  {pest}: {conf}% (agreement={agree}/{total})")
    if not preds:
        print("  (no detections)")
