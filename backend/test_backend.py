"""Backend integration test."""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 50)
print("SafeGuard AI Backend — Integration Test")
print("=" * 50)

# 1. Detection Engine
from detection.model import PPEDetector
import cv2
d = PPEDetector()
print("[OK] ONNX Model loaded")

imgs = glob.glob(r"i:\AntiGRavity\My_FYP_Dataset\test\images\*.jpg")
img = cv2.imread(imgs[0])
results = d.detect(img)
print(f"[OK] Detection: {len(results)} objects found")
for r in results:
    print(f"     - {r['class_name']}: {r['confidence']:.2f}")

# 2. Violation Logic
from detection.violation_logic import compute_violations
violations = compute_violations(results)
print(f"[OK] Violations: {len(violations)} persons evaluated")

# 3. Annotator
from detection.annotator import annotate_frame
annotated = annotate_frame(img.copy(), results, violations)
os.makedirs("screenshots", exist_ok=True)
cv2.imwrite("screenshots/test.jpg", annotated)
print("[OK] Annotator working — saved screenshots/test.jpg")

# 4. Database
from db.database import engine, Base, SessionLocal
Base.metadata.create_all(bind=engine)
print("[OK] Database created")

# 5. Config
from config import settings
print(f"[OK] Config loaded — Email: {'ON' if settings.ENABLE_EMAIL_ALERTS else 'OFF'}, WhatsApp: {'ON' if settings.ENABLE_WHATSAPP_ALERTS else 'OFF'}")

# 6. FastAPI import
from main import app
print(f"[OK] FastAPI app created — {len(app.routes)} routes")

print("\n" + "=" * 50)
print("ALL BACKEND TESTS PASSED!")
print("=" * 50)
