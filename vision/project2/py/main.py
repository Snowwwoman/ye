import subprocess
import os
import sys
import shutil
import time

# 切换到project2目录（使用脚本所在目录，兼容不同机器）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    os.chdir(BASE_DIR)
except Exception:
    pass
# Debug prints for VS Code run issues: interpreter and current working dir
print("DEBUG: sys.executable=", sys.executable)
print("DEBUG: cwd=", os.getcwd())

# --- Cleanup old generated data but keep original images ---
def cleanup_generated():
    to_remove_dirs = [
        os.path.join(BASE_DIR, 'data', 'test_run'),
        os.path.join(BASE_DIR, 'data', 'labels'),
        os.path.join(BASE_DIR, 'data', 'images3'),
        os.path.join(BASE_DIR, 'data', 'angle'),
        os.path.join(BASE_DIR, 'pick'),
        os.path.join(BASE_DIR, 'pixel_results'),
        os.path.join(BASE_DIR, 'end'),
    ]
    for p in to_remove_dirs:
        if os.path.isdir(p):
            try:
                shutil.rmtree(p)
                print(f"Removed directory: {p}")
            except Exception as e:
                print(f"Failed to remove {p}: {e}")
        elif os.path.isfile(p):
            try:
                os.remove(p)
                print(f"Removed file: {p}")
            except Exception as e:
                print(f"Failed to remove file {p}: {e}")

    # recreate minimal dirs
    os.makedirs(os.path.join(BASE_DIR, 'pick'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'pixel_results'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'end'), exist_ok=True)

print("Cleaning previous run outputs (keeps data/images)...")
cleanup_generated()
time.sleep(0.05)

# 步骤1: 运行testseg.py
print("Step 1: Running testseg.py")
subprocess.run([sys.executable, "testseg.py"], check=True)

# 步骤2: 运行cropdataset.py
print("Step 2: Running cropdataset.py")
subprocess.run([
    sys.executable, "cropdataset.py",
    "--source_dir", "data/images",
    "--labels_dir", "data/labels",
    "--dest_dir", "data/images3"
], check=True)

# 步骤3: 运行angle_calc.py
# 步骤4: 运行testseg2.py
print("Step 4: Running testseg2.py")
subprocess.run([sys.executable, "testseg2.py"], check=True)

# 步骤3: (moved) angle_calc will run after testseg2 so labels3 exist

# 步骤4: 运行testseg2.py
print("Step 4: Running testseg2.py")
subprocess.run([sys.executable, "testseg2.py"], check=True)

# 步骤5: 运行angle_calc.py (now after testseg2)
print("Step 5: Running angle_calc.py")
subprocess.run([sys.executable, "data/angle_calc.py"], check=True)

# 步骤6: 运行pick.py
print("Step 6: Running pick.py")
subprocess.run([sys.executable, "pick.py"], check=True)

# 步骤7: 转换到像素坐标
print("Step 7: Converting to pixel coordinates")
from PIL import Image
# pick newest image file in data/images (any common image ext)
img_dir = os.path.join(BASE_DIR, "data", "images")
img_path = None
if os.path.isdir(img_dir):
    exts = ('.bmp', '.png', '.jpg', '.jpeg')
    candidates = [os.path.join(img_dir, f) for f in os.listdir(img_dir) if f.lower().endswith(exts)]
    if candidates:
        img_path = max(candidates, key=lambda p: os.path.getmtime(p))

if not img_path or not os.path.exists(img_path):
    raise FileNotFoundError(f"No image found in {img_dir}")

img = Image.open(img_path)
img_w, img_h = img.size
print(f"Using image: {img_path}")
print(f"Image size: {img_w}x{img_h}")

def norm_to_pixel(x_norm, y_norm, img_w, img_h):
    x_px = x_norm * img_w
    y_px = y_norm * img_h
    return x_px, y_px

input_dir = "pick"
output_dir = "pixel_results"
os.makedirs(output_dir, exist_ok=True)

files = sorted(os.listdir(input_dir))
for file in files:
    if not file.endswith(".txt"):
        continue
    input_path = os.path.join(input_dir, file)
    output_path = os.path.join(output_dir, file)
    with open(input_path, "r") as f:
        line = f.readline().strip()
    if not line:
        continue
    x_norm, y_norm, angle = map(float, line.split())
    x_px, y_px = norm_to_pixel(x_norm, y_norm, img_w, img_h)
    with open(output_path, "w") as f:
        f.write(f"{x_px:.3f} {y_px:.3f} {angle:.6f}\n")
    print(f"Processed: {file}")

# 步骤7: 转换到机器人坐标
print("Step 7: Converting to robot coordinates")
import numpy as np

H_PATH = os.path.join(BASE_DIR, "BD", "pixel_to_robot_H.npy")
H = np.load(H_PATH)

def pixel_to_robot(u, v, H):
    p = np.array([u, v, 1.0], dtype=np.float64)
    pw = H @ p
    pw /= pw[2]
    return float(pw[0]), float(pw[1])

end_dir = "end"
os.makedirs(end_dir, exist_ok=True)

for file in files:
    if not file.endswith(".txt"):
        continue
    pixel_path = os.path.join(output_dir, file)
    end_path = os.path.join(end_dir, file)
    with open(pixel_path, "r") as f:
        line = f.readline().strip()
    x_px, y_px, angle = map(float, line.split())
    X, Y = pixel_to_robot(x_px, y_px, H)
    with open(end_path, "w") as f:
        f.write(f"{X:.3f} {Y:.3f} {angle:.6f}\n")
    print(f"Converted: {file} -> Robot: ({X:.3f}, {Y:.3f}), Angle: {angle:.6f}")

print("All steps completed. Results in 'end' directory.")
