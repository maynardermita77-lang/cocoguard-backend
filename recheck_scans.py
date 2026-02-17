from app.services.prediction_service import PestPredictionService as PredictionService
from PIL import Image
import os

svc = PredictionService()
svc.load_model()

for img_name in ['scan_20260216_174539_9eeee086.jpg', 'scan_20260216_175000_381b105c.jpg']:
    path = os.path.join('uploads', 'scans', img_name)
    if os.path.exists(path):
        img = Image.open(path)
        result = svc.predict(img)
        preds = result.get('predictions', [])
        print(f"\n{img_name}:")
        for p in preds[:3]:
            print(f"  {p['pest_type']}: {p['confidence']}%")
        if not preds:
            print("  (no detections)")
    else:
        print(f"{img_name}: NOT FOUND")
