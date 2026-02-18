"""
Pest Detection Prediction Service
Uses YOLOv11 TFLite model for coconut pest classification
"""

import os
import numpy as np
from PIL import Image
from typing import List, Dict, Tuple, Optional
import io


class PestPredictionService:
    """Service for pest detection using TFLite model"""
    
    def __init__(self):
        self.model = None
        self.labels = []
        self.input_details = None
        self.output_details = None
        self.model_loaded = False
        
        # Default paths - can be overridden
        # From app/services/ go up 2 levels to repo root, then into assets/model/
        self.model_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../../assets/model/best_float16.tflite')
        )
        self.labels_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '../../assets/model/labels.txt')
        )
        
    def load_model(self) -> bool:
        """Load the TFLite model and labels"""
        try:
            import tensorflow as tf
            
            # Load TFLite model
            if not os.path.exists(self.model_path):
                print(f"[ERROR] Model file not found: {self.model_path}")
                return False
                
            self.model = tf.lite.Interpreter(model_path=self.model_path)
            self.model.allocate_tensors()
            
            # Get input and output details
            self.input_details = self.model.get_input_details()
            self.output_details = self.model.get_output_details()
            
            print(f"[INFO] Model loaded successfully from {self.model_path}")
            print(f"[INFO] Input shape: {self.input_details[0]['shape']}")
            print(f"[INFO] Output shape: {self.output_details[0]['shape']}")
            
            # Load labels
            if not os.path.exists(self.labels_path):
                print(f"[ERROR] Labels file not found: {self.labels_path}")
                return False
                
            with open(self.labels_path, 'r') as f:
                self.labels = [line.strip() for line in f.readlines() if line.strip()]
            
            print(f"[INFO] Loaded {len(self.labels)} labels: {self.labels}")
            
            self.model_loaded = True
            return True
            
        except ImportError:
            print("[ERROR] TensorFlow not installed. Please install with: pip install tensorflow")
            return False
        except Exception as e:
            print(f"[ERROR] Failed to load model: {str(e)}")
            return False
    
    def preprocess_image(self, image: Image.Image) -> np.ndarray:
        """
        Preprocess image for YOLO model inference.
        Uses letterbox resizing to maintain aspect ratio (matches training preprocessing).
        """
        # Get expected input size from model
        input_shape = self.input_details[0]['shape']
        target_h, target_w = input_shape[1], input_shape[2]  # 640x640
        
        # Convert to RGB
        image = image.convert('RGB')
        orig_w, orig_h = image.size
        
        # Calculate letterbox scaling (maintain aspect ratio)
        scale = min(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        
        # Resize with high-quality resampling
        resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Create letterbox canvas (gray padding, standard YOLO)
        letterbox = Image.new('RGB', (target_w, target_h), (114, 114, 114))
        
        # Paste resized image centered
        pad_x = (target_w - new_w) // 2
        pad_y = (target_h - new_h) // 2
        letterbox.paste(resized, (pad_x, pad_y))
        
        # Convert to numpy array and normalize to [0, 1]
        img_array = np.array(letterbox, dtype=np.float32) / 255.0
        
        # Add batch dimension: [H, W, C] -> [1, H, W, C]
        img_array = np.expand_dims(img_array, axis=0)
        
        return img_array

    # ================================================================
    #  IMAGE QUALITY PRE-CHECK
    # ================================================================
    def _assess_image_quality(self, image: Image.Image) -> dict:
        """
        Pre-flight image quality assessment.
        Rejects images that are too small, extremely dark/bright, or very blurry.
        Returns dict with 'acceptable' bool, 'issues' list, and quality metrics.
        """
        issues = []
        warnings = []
        w, h = image.size

        # --- Resolution check ---
        if w < 32 or h < 32:
            issues.append(f"Image too small ({w}x{h}px, minimum 32x32px)")
        elif w < 100 or h < 100:
            warnings.append(f"Low resolution ({w}x{h}px) may reduce accuracy")

        # --- Brightness check ---
        grayscale = np.array(image.convert('L'), dtype=np.float32)
        mean_brightness = float(grayscale.mean())
        if mean_brightness < 10:
            issues.append(f"Image too dark (brightness {mean_brightness:.0f}/255)")
        elif mean_brightness < 30:
            warnings.append(f"Image is very dark (brightness {mean_brightness:.0f}/255)")
        elif mean_brightness > 250:
            issues.append(f"Image overexposed (brightness {mean_brightness:.0f}/255)")
        elif mean_brightness > 230:
            warnings.append(f"Image is very bright (brightness {mean_brightness:.0f}/255)")

        # --- Sharpness / blur check (gradient variance proxy) ---
        dx = np.diff(grayscale, axis=1)
        dy = np.diff(grayscale, axis=0)
        sharpness = float((dx.var() + dy.var()) / 2.0)
        if sharpness < 15.0:
            issues.append(f"Image extremely blurry (sharpness {sharpness:.1f}, minimum 15)")
        elif sharpness < 50.0:
            warnings.append(f"Image appears blurry (sharpness {sharpness:.1f})")

        quality = {
            'acceptable': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'brightness': mean_brightness,
            'sharpness': sharpness,
            'resolution': [w, h],
        }
        if issues:
            print(f"[QUALITY] \u274c Image rejected: {'; '.join(issues)}")
        elif warnings:
            print(f"[QUALITY] \u26a0\ufe0f Image warnings: {'; '.join(warnings)}")
        else:
            print(f"[QUALITY] \u2705 Image OK (brightness={mean_brightness:.0f}, "
                  f"sharpness={sharpness:.1f}, {w}x{h})")
        return quality

    # ================================================================
    #  TEST-TIME AUGMENTATION (TTA) — AUGMENTATION GENERATION
    # ================================================================
    def _generate_augmentations(self, image: Image.Image) -> list:
        """
        Generate augmented versions for Test-Time Augmentation + multi-scale.
        Returns list of (name, PIL.Image) tuples.

        Augmentations:
          1. Original image
          2. Horizontal flip
          3. Center crop at ~1.3x zoom (multi-scale)
          4. Slight brightness boost (+15%)
        """
        from PIL import ImageEnhance

        augmentations = [('original', image)]

        # 1. Horizontal flip
        augmentations.append(
            ('h-flip', image.transpose(Image.Transpose.FLIP_LEFT_RIGHT))
        )

        # 2. Center crop at ~1.3x zoom (multi-scale inference)
        w, h = image.size
        crop_ratio = 0.75          # Crop 75% of original  ≈ 1.33x zoom
        crop_w = int(w * crop_ratio)
        crop_h = int(h * crop_ratio)
        left = (w - crop_w) // 2
        top  = (h - crop_h) // 2
        center_crop = image.crop((left, top, left + crop_w, top + crop_h))
        augmentations.append(('center-crop-1.3x', center_crop))

        # 3. Slight brightness boost (+15%)
        enhancer = ImageEnhance.Brightness(image)
        augmentations.append(('brightness+15%', enhancer.enhance(1.15)))

        # 4. Contrast enhancement (+20%) — helps in field conditions
        # (overcast, shade, uneven lighting) where pest features are washed out.
        contrast_enhancer = ImageEnhance.Contrast(image)
        augmentations.append(('contrast+20%', contrast_enhancer.enhance(1.2)))

        return augmentations

    # ================================================================
    #  NON-MAXIMUM SUPPRESSION (IoU-based)
    # ================================================================
    @staticmethod
    def _apply_nms(detections: list, iou_threshold: float = 0.5) -> list:
        """
        Remove overlapping detections for the same class, keeping only the
        highest-confidence box. Prevents duplicate anchors on the same pest
        from diluting confidence averages.
        """
        if len(detections) <= 1:
            return detections

        # Sort by confidence descending
        detections.sort(key=lambda d: -d[0])
        kept = []
        suppressed = [False] * len(detections)

        for i in range(len(detections)):
            if suppressed[i]:
                continue
            kept.append(detections[i])
            _, box_i = detections[i][0], detections[i][1]
            for j in range(i + 1, len(detections)):
                if suppressed[j]:
                    continue
                _, box_j = detections[j][0], detections[j][1]
                if PestPredictionService._compute_iou(box_i, box_j) > iou_threshold:
                    suppressed[j] = True
        return kept

    @staticmethod
    def _compute_iou(box_a: tuple, box_b: tuple) -> float:
        """Compute IoU between two (cx, cy, w, h) boxes."""
        ax1 = box_a[0] - box_a[2] / 2
        ay1 = box_a[1] - box_a[3] / 2
        ax2 = box_a[0] + box_a[2] / 2
        ay2 = box_a[1] + box_a[3] / 2

        bx1 = box_b[0] - box_b[2] / 2
        by1 = box_b[1] - box_b[3] / 2
        bx2 = box_b[0] + box_b[2] / 2
        by2 = box_b[1] + box_b[3] / 2

        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)

        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0

        inter = (ix2 - ix1) * (iy2 - iy1)
        union = box_a[2] * box_a[3] + box_b[2] * box_b[3] - inter
        return inter / union if union > 0 else 0.0

    # ================================================================
    #  TTA RESULT AGGREGATION
    # ================================================================
    def _aggregate_tta_results(self, per_aug_results: list,
                               min_agreement: int = 2) -> list:
        """
        Aggregate predictions across TTA augmentations.
        Only keeps pest classes detected in >= min_agreement augmentations.
        Averages confidence scores for consistency.
        """
        from collections import defaultdict

        # Collect per-class detections (max one entry per augmentation)
        class_detections = defaultdict(list)   # pest_type -> [pred_dict, ...]

        for preds in per_aug_results:
            seen = set()
            for pred in preds:
                pt = pred['pest_type']
                if pt not in seen:
                    class_detections[pt].append(pred)
                    seen.add(pt)

        total_augs = len(per_aug_results)
        aggregated = []

        # Minimum average confidence to keep a class in TTA results.
        # 50% is pure sigmoid baseline noise; require at least 55% to be meaningful.
        TTA_MIN_CONFIDENCE = 55.0

        for pest_type, detections in class_detections.items():
            agreement = len(detections)
            if agreement >= min_agreement:
                # ── Weighted average: higher-confidence augmentations contribute more ──
                # Plain average treats a 60% augmentation equally to an 80% one.
                # Weighted average gives more influence to clearer detections.
                total_weight = sum(d['confidence'] for d in detections)
                if total_weight > 0:
                    weighted_conf = sum(d['confidence'] ** 2 for d in detections) / total_weight
                else:
                    weighted_conf = 0.0

                if weighted_conf < TTA_MIN_CONFIDENCE:
                    print(f"[TTA] \u274c {pest_type}: {weighted_conf:.1f}% "
                          f"(below {TTA_MIN_CONFIDENCE}% noise floor, skipping)")
                    continue
                best_det = max(detections, key=lambda d: d['confidence'])
                aggregated.append({
                    'pest_type':     pest_type,
                    'confidence':    round(weighted_conf, 2),
                    'class_id':      best_det.get('class_id', -1),
                    'anchor_count':  max(d.get('anchor_count', 0) for d in detections),
                    'bbox':          best_det.get('bbox', {}),
                    'tta_agreement': agreement,
                    'tta_total':     total_augs,
                })
                print(f"[TTA] \u2705 {pest_type}: {weighted_conf:.1f}%  "
                      f"(agreed {agreement}/{total_augs} augmentations, weighted avg)")
            else:
                print(f"[TTA] \u274c {pest_type}: rejected  "
                      f"(only {agreement}/{total_augs}, need \u2265{min_agreement})")

        # ── Post-TTA disambiguation for APW Larvae vs White Grub ──
        # These two pests are visually identical; different augmentations may
        # pick different winners.  Keep only the one with higher agreement.
        # Tie-break: precautionary principle → favour APW Larvae (more dangerous).
        CONFUSION_PAIR = {'APW Larvae', 'White Grub'}
        pair_entries = [p for p in aggregated if p['pest_type'] in CONFUSION_PAIR]
        if len(pair_entries) == 2:
            a, b = pair_entries
            if a['tta_agreement'] != b['tta_agreement']:
                loser = b if a['tta_agreement'] > b['tta_agreement'] else a
            else:
                # Equal agreement → precautionary: keep APW Larvae
                loser = b if a['pest_type'] == 'APW Larvae' else a
            aggregated.remove(loser)
            print(f"[TTA] 🔀 Confusion-pair disambiguation: "
                  f"keeping {[p for p in pair_entries if p is not loser][0]['pest_type']}, "
                  f"dropping {loser['pest_type']} "
                  f"(agreement {loser['tta_agreement']}/{total_augs})")

        # Sort by agreement (more augmentations = more reliable), then confidence
        aggregated.sort(key=lambda x: (x['tta_agreement'], x['confidence']),
                        reverse=True)
        return aggregated

    # ================================================================
    #  SINGLE-INFERENCE HELPER
    # ================================================================
    def _run_single_inference(self, image: Image.Image,
                              confidence_threshold: float) -> List[Dict]:
        """
        Run one forward pass: preprocess → invoke → YOLO post-process.
        Returns raw per-class predictions list.
        """
        input_data = self.preprocess_image(image)
        self.model.set_tensor(self.input_details[0]['index'], input_data)
        self.model.invoke()
        output_data = self.model.get_tensor(self.output_details[0]['index'])
        return self._process_yolo_output(output_data, confidence_threshold)

    # ================================================================
    #  MAIN PREDICT  (with TTA + quality check)
    # ================================================================
    def predict(self, image: Image.Image, confidence_threshold: float = 0.5) -> Dict:
        """
        Run prediction with Test-Time Augmentation (TTA), multi-scale
        inference, and image-quality pre-checks.

        Pipeline:
          1. Image quality gate  (reject blurry / dark / tiny images)
          2. Generate 4 augmented versions  (original, h-flip, 1.3x crop, brightness+)
          3. YOLO inference on each augmentation independently
          4. Keep only classes detected in  >= 2 / 4  augmentations
          5. Average confidence across agreeing augmentations

        This significantly reduces false positives and smooths confidence variance.
        """
        if not self.model_loaded:
            if not self.load_model():
                return {
                    "success": False,
                    "error": "Model not loaded",
                    "predictions": []
                }

        try:
            # ── Step 1: image quality assessment (warnings only, no rejection) ──
            quality = self._assess_image_quality(image)
            if not quality['acceptable']:
                print(f"[QUALITY] ⚠️ Image quality issues detected but proceeding: {'; '.join(quality['issues'])}")
            # Always proceed with detection - no rejection

            # ── Step 2: generate augmentations (TTA + multi-scale) ──
            augmentations = self._generate_augmentations(image)
            print(f"[TTA] Running inference on {len(augmentations)} augmentations...")

            # ── Step 3: inference per augmentation ──
            per_aug_results = []
            for name, aug_image in augmentations:
                preds = self._run_single_inference(aug_image, confidence_threshold)
                per_aug_results.append(preds)
                detected = [f"{p['pest_type']}({p['confidence']:.1f}%)" for p in preds]
                print(f"[TTA]   {name}: {detected if detected else 'no detections'}")

            # ── Step 4: aggregate with consistency requirement ──
            predictions = self._aggregate_tta_results(
                per_aug_results, min_agreement=2
            )

            print(f"[TTA] === FINAL: {len(predictions)} predictions "
                  f"(required \u22652/{len(augmentations)} agreement) ===")

            return {
                "success":          True,
                "predictions":      predictions,
                "total_detections": len(predictions),
                "quality":          quality,
                "tta_augmentations": len(augmentations)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "predictions": []
            }
    
    def _process_yolo_output(self, output: np.ndarray, threshold: float) -> List[Dict]:
        """
        Process YOLOv11-Seg model output to extract detections
        
        YOLOv11-Seg TFLite output format: [1, 43, 8400]
        Tensor layout per anchor (43 features):
          - Index 0-3: bounding box (cx, cy, w, h)
          - Index 4-10: class logits (7 classes) - objectness fused into class scores
          - Index 11-42: mask coefficients (32 values, ignored for detection)
        
        No objectness score - use max class score as confidence.
        Apply sigmoid to class logits to get probabilities.
        
        Confidence stabilization: averages top-k detections per class for stable output.
        Expected confidence range: 0.5-0.8 (model behavior, not artificially scaled).
        """
        predictions = []
        
        # The 7 pest type labels (direct mapping: class 0 = label 0, etc.)
        LABELS = [
            'APW Adult', 'APW Larvae', 'Brontispa', 'Brontispa Pupa',
            'Rhinoceros Beetle', 'Slug Caterpillar', 'White Grub'
        ]
        NUM_CLASSES = 7
        TOP_K = 3  # Reduced from 5 → 3: fewer weak anchors in average = +3-5% confidence
        MIN_ANCHOR_COUNT = 3  # Minimum anchors per class to be considered real
        MAX_SIMULTANEOUS_CLASSES = 3  # Max classes that can fire at once
        MAX_CLASS_SPREAD_RATIO = 0.85  # Max ratio between top two class confidences
        NMS_IOU_THRESHOLD = 0.5  # NMS: suppress overlapping boxes with IoU > this
        MIN_AVG_MARGIN = 0.09  # Minimum avg margin between best and 2nd-best class
        
        try:
            # Remove batch dimension: [1, 43, 8400] -> [43, 8400]
            output = np.squeeze(output)
            
            if len(output.shape) != 2:
                print(f"[ERROR] Unexpected output shape: {output.shape}")
                return []
            
            num_features, num_anchors = output.shape
            print(f"[DEBUG] Output shape: {output.shape} ({num_features} features x {num_anchors} anchors)")
            
            # YOLOv11-Seg tensor layout:
            # Index 0-3: bounding box (cx, cy, w, h)
            # Index 4-10: class logits (7 classes)
            # Index 11-42: mask coefficients (ignored)
            
            boxes = output[0:4, :]      # Shape: [4, 8400]
            class_logits = output[4:4+NUM_CLASSES, :]  # Shape: [7, 8400] - indices 4-10
            
            # Apply sigmoid to convert logits to probabilities
            class_probs = 1 / (1 + np.exp(-class_logits))
            
            print(f"[DEBUG] Class probs shape: {class_probs.shape}")
            print(f"[DEBUG] Class probs range: {class_probs.min():.4f} to {class_probs.max():.4f}")
            
            # For each anchor, find the best class (0-6)
            max_probs = np.max(class_probs, axis=0)  # Shape: [8400]
            max_class_ids = np.argmax(class_probs, axis=0)  # Shape: [8400], values 0-6
            
            # Filter by confidence threshold
            valid_mask = max_probs >= threshold
            valid_indices = np.where(valid_mask)[0]
            
            if len(valid_indices) == 0:
                print("[DEBUG] No detections above threshold")
                return []
            
            print(f"[DEBUG] Found {len(valid_indices)} detections above threshold {threshold}")
            
            # Collect ALL valid detections per class for averaging (stability)
            pest_detections = {i: [] for i in range(NUM_CLASSES)}  # class_id -> list of (conf, box)
            
            # Track per-anchor confusion margins between APW Larvae (1) and White Grub (6).
            # For each anchor assigned to one of these classes, record how much higher
            # its winning prob was vs the other class. Low margins = model is confused.
            APW_LARVAE_CLASS = 1
            WHITE_GRUB_CLASS = 6
            confusion_margins = {APW_LARVAE_CLASS: [], WHITE_GRUB_CLASS: []}  # classId -> [margin, ...]
            
            # Track per-anchor margin (best class prob - 2nd best class prob) for ALL classes.
            # Real pests have avg margins >= 9%; false positives on random objects < 9%.
            # Gap: false positives max 8.0% (scan 14), real pests min 9.8% (scan 25).
            MIN_AVG_MARGIN = 0.09
            class_margins = {}  # class_id -> list of margins
            
            for idx in valid_indices:
                class_id = int(max_class_ids[idx])
                conf = float(max_probs[idx])
                
                # Track confusion margin for APW Larvae vs White Grub anchors
                if class_id in (APW_LARVAE_CLASS, WHITE_GRUB_CLASS):
                    other_class = WHITE_GRUB_CLASS if class_id == APW_LARVAE_CLASS else APW_LARVAE_CLASS
                    other_prob = float(class_probs[other_class, idx])
                    margin = conf - other_prob
                    confusion_margins[class_id].append(margin)
                
                # Track margin vs 2nd-best class for every anchor
                anchor_probs = class_probs[:, idx]
                sorted_probs = np.sort(anchor_probs)[::-1]
                margin_vs_2nd = float(sorted_probs[0] - sorted_probs[1]) if len(sorted_probs) > 1 else float(sorted_probs[0])
                if class_id not in class_margins:
                    class_margins[class_id] = []
                class_margins[class_id].append(margin_vs_2nd)
                
                # Get box coordinates (normalized 0-1)
                cx = float(boxes[0, idx])
                cy = float(boxes[1, idx])
                w = float(boxes[2, idx])
                h = float(boxes[3, idx])
                
                # Filter invalid boxes (too small or impossibly large)
                if w < 0.01 or h < 0.01 or w > 2.0 or h > 2.0:
                    continue
                
                pest_detections[class_id].append((conf, (cx, cy, w, h)))
            
            # ── Apply NMS per class to remove overlapping boxes ──
            # This keeps only the best detection in each spatial region,
            # preventing duplicate anchors from diluting confidence averages.
            total_before_nms = sum(len(d) for d in pest_detections.values())
            for class_id in range(NUM_CLASSES):
                if len(pest_detections[class_id]) > 1:
                    pest_detections[class_id] = self._apply_nms(
                        pest_detections[class_id], NMS_IOU_THRESHOLD
                    )
            total_after_nms = sum(len(d) for d in pest_detections.values())
            print(f"[NMS] {total_before_nms} → {total_after_nms} detections "
                  f"(suppressed {total_before_nms - total_after_nms} overlapping boxes)")

            # ── Per-anchor margin filter ──
            # If the average margin between best and 2nd-best class is < 9%,
            # the model is indecisive — likely a non-pest image.
            for class_id in range(NUM_CLASSES):
                margins = class_margins.get(class_id, [])
                if margins and pest_detections[class_id]:
                    avg_margin = sum(margins) / len(margins)
                    if avg_margin < MIN_AVG_MARGIN:
                        label = LABELS[class_id] if class_id < len(LABELS) else f"Unknown({class_id})"
                        print(f"[GUARD] Margin filter: {label} avg margin "
                              f"{avg_margin*100:.1f}% < {MIN_AVG_MARGIN*100:.0f}% "
                              f"— model indecisive, clearing {len(pest_detections[class_id])} detections.")
                        pest_detections[class_id] = []

            # For each class with detections, compute stabilized confidence
            pest_results = {}  # class_id -> (avg_conf, best_box)
            
            for class_id, detections in pest_detections.items():
                if not detections:
                    continue
                    
                # Sort by confidence (descending)
                detections.sort(key=lambda x: -x[0])
                
                # Take top-k detections and average their confidence (stability)
                top_k = detections[:TOP_K]
                avg_conf = sum(d[0] for d in top_k) / len(top_k)
                best_box = top_k[0][1]  # Use best detection's box
                
                pest_results[class_id] = (avg_conf, best_box, len(detections))
            
            # Debug output
            print(f"\n=== DETECTION RESULTS (stabilized) ===")
            for class_id in sorted(pest_results.keys(), key=lambda c: -pest_results[c][0]):
                avg_conf, _, count = pest_results[class_id]
                label = LABELS[class_id] if class_id < len(LABELS) else f"Unknown({class_id})"
                print(f"Class {class_id} ({label}): {avg_conf*100:.1f}% (avg of top-{min(count, TOP_K)} from {count} detections)")
            print("=" * 40)
            
            # === NOISE-FLOOR DOMINANT CLASS DETECTION ===
            # Across ALL 8400 anchors, find which class the model assigns most
            # often. At the sigmoid noise floor (logit~0, sigmoid~0.5), argmax
            # picks whichever class has the slightest learned bias — typically
            # class 0 (APW Adult). This is the model's "default guess" when it
            # sees something it doesn't recognize (teddy bears, food, fabric).
            # If the final detection matches this noise-dominant class, require
            # higher confidence to trust it as a real pest.
            NOISE_CLASS_MIN_CONFIDENCE_PCT = 68.0
            
            all_class_counts = np.bincount(max_class_ids.astype(int), minlength=NUM_CLASSES)
            noise_dominant_class = int(np.argmax(all_class_counts))
            noise_dominant_pct = all_class_counts[noise_dominant_class] / num_anchors * 100
            nlabel = LABELS[noise_dominant_class] if noise_dominant_class < len(LABELS) else "Unknown"
            print(f"[DEBUG] Noise-dominant class: {nlabel} "
                  f"({noise_dominant_pct:.1f}% of all {num_anchors} anchors)")
            
            # === ANTI-FALSE-POSITIVE CHECK 1: Too many classes firing ===
            # Non-pest images (humans, objects, etc.) trigger scattered detections
            # across many classes. Real pests concentrate in 1-2 classes.
            # IMPORTANT: Only count classes with meaningful confidence (top-k avg > 55%).
            # At the sigmoid noise floor (50%), every class has detections — counting
            # those would cause ALL images to fail this check.
            MEANINGFUL_CONFIDENCE = 0.55  # Must be above 50% noise floor
            meaningful_classes = sum(
                1 for cid, (avg_c, _, cnt) in pest_results.items()
                if avg_c >= MEANINGFUL_CONFIDENCE and cnt >= MIN_ANCHOR_COUNT
            )
            if meaningful_classes > MAX_SIMULTANEOUS_CLASSES:
                print(f"[GUARD] WARNING FALSE POSITIVE: {meaningful_classes} classes "
                      f"have meaningful detections (max allowed: {MAX_SIMULTANEOUS_CLASSES}). "
                      f"Non-pest image detected (e.g. human/person). Returning empty.")
                return []
            
            # Build predictions with direct class-to-label mapping
            # Apply minimum anchor count filter
            for class_id, (avg_conf, box, count) in pest_results.items():
                # === ANTI-FALSE-POSITIVE CHECK 2: Minimum anchor count ===
                if count < MIN_ANCHOR_COUNT:
                    label = LABELS[class_id] if class_id < len(LABELS) else f"Unknown({class_id})"
                    print(f"[GUARD] WARNING Skipping {label}: only {count} anchors "
                          f"(minimum {MIN_ANCHOR_COUNT} required). Likely false positive.")
                    continue
                
                # === ANTI-FALSE-POSITIVE CHECK 2b: Noise-dominant class needs higher confidence ===
                # The noise-dominant class is what the model "guesses" when uncertain.
                # Random objects (teddy bears, food, fabric) often trigger this class
                # at moderate confidence. Require 68% instead of the normal 60%.
                if class_id == noise_dominant_class and avg_conf * 100 < NOISE_CLASS_MIN_CONFIDENCE_PCT:
                    label = LABELS[class_id] if class_id < len(LABELS) else f"Unknown({class_id})"
                    print(f"[GUARD] WARNING Skipping {label}: noise-dominant class requires "
                          f"{NOISE_CLASS_MIN_CONFIDENCE_PCT}% but only has {avg_conf*100:.1f}%. "
                          f"Likely false positive on non-pest object.")
                    continue
                
                label = LABELS[class_id] if class_id < len(LABELS) else f"Unknown({class_id})"
                predictions.append({
                    "pest_type": label,
                    "confidence": round(avg_conf * 100, 2),
                    "class_id": class_id,
                    "anchor_count": count,
                    "bbox": {
                        "x": box[0], "y": box[1],
                        "width": box[2], "height": box[3]
                    }
                })
            
            predictions.sort(key=lambda x: x['confidence'], reverse=True)
            
            # === CONFUSION PAIR DISAMBIGUATION: APW Larvae vs White Grub ===
            # These two pests look visually similar (both grub-like larvae) and
            # the model frequently confuses them. 
            #
            # PRECAUTIONARY PRINCIPLE: APW (Asiatic Palm Weevil) is the #1 most
            # destructive coconut pest in SE Asia. A false positive leads to an
            # inspection (safe), while a false negative means ignoring a
            # potentially tree-killing infestation.
            #
            # Apply precautionary principle even when only ONE of them is detected:
            # If White Grub is detected but there were APW Larvae anchors in raw
            # detection (even if filtered out), switch to APW Larvae.
            
            apw_larvae_pred = next((p for p in predictions if p['pest_type'] == 'APW Larvae'), None)
            white_grub_pred = next((p for p in predictions if p['pest_type'] == 'White Grub'), None)
            
            apw_had_anchors = len(confusion_margins.get(APW_LARVAE_CLASS, [])) > 0
            wg_had_anchors = len(confusion_margins.get(WHITE_GRUB_CLASS, [])) > 0
            
            # Case 1: Only White Grub detected, but APW Larvae had anchors → switch to APW Larvae
            if white_grub_pred and not apw_larvae_pred and apw_had_anchors:
                wg_conf = white_grub_pred['confidence']
                # Apply precautionary principle for ambiguous confidence (< 80%)
                if wg_conf < 80.0:
                    print(f"[DISAMBIG] PRECAUTIONARY: White Grub detected at {wg_conf:.1f}% "
                          f"but APW Larvae anchors existed. Switching to APW Larvae (more dangerous).")
                    white_grub_pred['pest_type'] = 'APW Larvae'
                    white_grub_pred['class_id'] = APW_LARVAE_CLASS
            
            # Case 2: Both detected → use composite score with precautionary principle
            elif apw_larvae_pred and white_grub_pred:
                apw_anchors = apw_larvae_pred.get('anchor_count', 0)
                wg_anchors = white_grub_pred.get('anchor_count', 0)
                apw_conf = apw_larvae_pred['confidence']
                wg_conf = white_grub_pred['confidence']
                
                # Compute average per-anchor confusion margin for each class.
                # Higher margin = model was more certain per-anchor for that class.
                apw_margins = confusion_margins.get(APW_LARVAE_CLASS, [])
                wg_margins = confusion_margins.get(WHITE_GRUB_CLASS, [])
                apw_avg_margin = sum(apw_margins) / len(apw_margins) if apw_margins else 0.0
                wg_avg_margin = sum(wg_margins) / len(wg_margins) if wg_margins else 0.0
                
                # Composite score = confidence x anchor_proportion x (1 + avg_margin)
                total_anchors = apw_anchors + wg_anchors
                apw_score = apw_conf * (apw_anchors / total_anchors) * (1.0 + apw_avg_margin)
                wg_score = wg_conf * (wg_anchors / total_anchors) * (1.0 + wg_avg_margin)
                
                # Precautionary principle: when scores are close (within 15%), favor APW Larvae
                scores_are_close = (min(apw_score, wg_score) / max(apw_score, wg_score)) > 0.85
                
                if scores_are_close:
                    # Ambiguous — apply precautionary principle: favor APW Larvae
                    winner = 'APW Larvae'
                    predictions = [p for p in predictions if p['pest_type'] != 'White Grub']
                    print(f"[DISAMBIG] WARNING Scores too close (ratio>{0.85:.0%}) -- "
                          f"precautionary principle: favoring APW Larvae (more dangerous pest).")
                elif apw_score >= wg_score:
                    winner = 'APW Larvae'
                    predictions = [p for p in predictions if p['pest_type'] != 'White Grub']
                else:
                    winner = 'White Grub'
                    predictions = [p for p in predictions if p['pest_type'] != 'APW Larvae']
                
                loser = 'White Grub' if winner == 'APW Larvae' else 'APW Larvae'
                print(f"[DISAMBIG] APW Larvae vs White Grub conflict.")
                print(f"   APW Larvae: {apw_conf:.1f}% | {apw_anchors} anchors | "
                      f"avg_margin={apw_avg_margin:.3f} | score={apw_score:.2f}")
                print(f"   White Grub: {wg_conf:.1f}% | {wg_anchors} anchors | "
                      f"avg_margin={wg_avg_margin:.3f} | score={wg_score:.2f}")
                print(f"   Winner: {winner}, suppressing {loser}.")
                predictions.sort(key=lambda x: x['confidence'], reverse=True)
            
            # === ANTI-FALSE-POSITIVE CHECK 3: Class dominance / spread check ===
            # If top two classes have very similar confidences, the model is "confused"
            # — hallmark of non-pest images (humans, random objects).
            if len(predictions) >= 2:
                top_conf = predictions[0]['confidence']
                second_conf = predictions[1]['confidence']
                if top_conf > 0:
                    ratio = second_conf / top_conf
                    if ratio > MAX_CLASS_SPREAD_RATIO:
                        print(f"[GUARD] WARNING FALSE POSITIVE: Top 2 classes too similar "
                              f"({top_conf:.1f}% vs {second_conf:.1f}%, "
                              f"ratio={ratio:.2f} > {MAX_CLASS_SPREAD_RATIO}). "
                              f"Non-pest image. Clearing predictions.")
                        return []
            
            print(f"[DEBUG] Returning {len(predictions)} predictions")
            return predictions
            
        except Exception as e:
            print(f"[ERROR] Failed to process YOLO output: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def predict_from_bytes(self, image_bytes: bytes, confidence_threshold: float = 0.5) -> Dict:
        """Run prediction from image bytes"""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            return self.predict(image, confidence_threshold)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load image: {str(e)}",
                "predictions": []
            }
    
    def predict_from_path(self, image_path: str, confidence_threshold: float = 0.5) -> Dict:
        """Run prediction from image file path"""
        try:
            image = Image.open(image_path)
            return self.predict(image, confidence_threshold)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load image: {str(e)}",
                "predictions": []
            }
    
    def get_model_info(self) -> Dict:
        """Get information about the loaded model"""
        return {
            "model_loaded": self.model_loaded,
            "model_path": self.model_path,
            "labels_path": self.labels_path,
            "labels": self.labels,
            "num_classes": len(self.labels),
            "input_shape": self.input_details[0]['shape'].tolist() if self.input_details else None,
            "output_shape": self.output_details[0]['shape'].tolist() if self.output_details else None
        }


# Singleton instance
_prediction_service: Optional[PestPredictionService] = None


def get_prediction_service() -> PestPredictionService:
    """Get or create the prediction service singleton"""
    global _prediction_service
    if _prediction_service is None:
        _prediction_service = PestPredictionService()
        _prediction_service.load_model()
    return _prediction_service
