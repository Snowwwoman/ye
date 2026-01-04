import subprocess
import os
import sys
import shutil
import time
from ultralytics import YOLO
from PIL import Image
import math
import numpy as np
from glob import glob

# 切换到project2目录（使用脚本所在目录，兼容不同机器）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    os.chdir(BASE_DIR)
except Exception:
    pass
# Debug prints for VS Code run issues: interpreter and interpreter and current working dir
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

# Integrated step functions
def run_testseg():
    """Step 1: Run segmentation on newest image"""
    print("Step 1: Running segmentation on newest image")

    MODEL_PATH = os.path.join(BASE_DIR, "best.pt")
    IMAGES_DIR = os.path.join(BASE_DIR, "data", "images")
    TEMP_SAVE_DIR = os.path.join(BASE_DIR, "data")
    FINAL_LABELS_DIR = os.path.join(BASE_DIR, "data", "labels")

    os.makedirs(TEMP_SAVE_DIR, exist_ok=True)
    os.makedirs(FINAL_LABELS_DIR, exist_ok=True)

    model = YOLO(MODEL_PATH)

    def find_newest_image(images_dir):
        if not os.path.isdir(images_dir):
            return None
        exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
        candidates = []
        for name in os.listdir(images_dir):
            path = os.path.join(images_dir, name)
            if os.path.isfile(path) and os.path.splitext(name)[1].lower() in exts:
                candidates.append(path)
        if not candidates:
            return None
        return max(candidates, key=lambda p: os.path.getmtime(p))

    newest = find_newest_image(IMAGES_DIR)
    if newest is None:
        print(f"⚠️ 没有找到图片，目录: {IMAGES_DIR}")
        return

    print(f"🔎 使用最新图片进行推理: {newest}")

    results = model.predict(
        source=newest,
        save=True,
        save_txt=True,
        project=TEMP_SAVE_DIR,
        name="test_run",
        exist_ok=True,
        device='cpu',
        imgsz=640,
        conf=0.40,
        iou=0.6
    )

    pred_labels_dir = os.path.join(TEMP_SAVE_DIR, "test_run", "labels")
    base = os.path.splitext(os.path.basename(newest))[0]
    pred_txt = os.path.join(pred_labels_dir, base + ".txt")

    if os.path.exists(pred_txt):
        shutil.copy(pred_txt, FINAL_LABELS_DIR)
        print(f"✅ 推理完成，标签已复制到: {FINAL_LABELS_DIR}")

def crop_images_single_target(source_dir, labels_dir, dest_dir):
    """Step 2: Crop images based on labels"""
    print("Step 2: Cropping images based on labels")

    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)

    img_sub = source_dir
    lbl_sub = labels_dir

    out_img_sub = os.path.join(dest_dir, 'images')
    out_lbl_sub = os.path.join(dest_dir, 'labels')
    orig_lbl_sub = os.path.join(dest_dir, 'orig_labels')

    os.makedirs(out_img_sub, exist_ok=True)
    os.makedirs(out_lbl_sub, exist_ok=True)
    os.makedirs(orig_lbl_sub, exist_ok=True)

    for root, dirs, files in os.walk(img_sub):
        for file in files:
            if not file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                continue

            base = os.path.splitext(file)[0]
            img_path = os.path.join(root, file)
            txt_path = os.path.join(lbl_sub, base + '.txt')

            if not os.path.exists(txt_path):
                continue

            img = Image.open(img_path)
            w, h = img.size

            with open(txt_path, 'r') as f:
                lines = f.readlines()

            for i, line in enumerate(lines):
                parts = line.strip().split()
                if len(parts) < 5:
                    continue

                class_id = parts[0]
                coords = parts[1:]

                if len(coords) % 2 != 0:
                    continue

                try:
                    coords_float = [float(c) for c in coords]
                except ValueError:
                    continue

                xs = coords_float[::2]
                ys = coords_float[1::2]

                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)

                left = int(min_x * w)
                right = int(max_x * w)
                upper = int(min_y * h)
                lower = int(max_y * h)

                if left >= right or upper >= lower:
                    continue

                crop_img = img.crop((left, upper, right, lower))
                crop_name = f'{base}_{i}.jpg'
                crop_img.save(os.path.join(out_img_sub, crop_name))

                # 原 label
                with open(os.path.join(orig_lbl_sub, crop_name[:-4] + '.txt'), 'w') as f2:
                    f2.write(line)

                # 调整后的坐标
                new_coords = []
                crop_w = right - left
                crop_h = lower - upper

                for j in range(0, len(coords_float), 2):
                    x, y = coords_float[j], coords_float[j+1]
                    new_x = max(0.0, min(1.0, (x * w - left) / crop_w))
                    new_y = max(0.0, min(1.0, (y * h - upper) / crop_h))
                    new_coords.append(f"{new_x:.6f}")
                    new_coords.append(f"{new_y:.6f}")

                new_line = ' '.join([class_id] + new_coords) + '\n'
                with open(os.path.join(out_lbl_sub, crop_name[:-4] + '.txt'), 'w') as f3:
                    f3.write(new_line)

def run_testseg2():
    """Step 3: Run segmentation on cropped images"""
    print("Step 3: Running segmentation on cropped images")

    MODEL_PATH = os.path.join(BASE_DIR, "2best.pt")
    IMAGES_DIR = os.path.join(BASE_DIR, "data", "images3", "images")
    TEMP_SAVE_DIR = os.path.join(BASE_DIR, "data", "images3")
    FINAL_LABELS_DIR = os.path.join(BASE_DIR, "data", "images3", "labels3")

    os.makedirs(TEMP_SAVE_DIR, exist_ok=True)
    os.makedirs(FINAL_LABELS_DIR, exist_ok=True)

    model = YOLO(MODEL_PATH)

    results = model.predict(
        source=IMAGES_DIR,
        save=True,
        save_txt=True,
        project=TEMP_SAVE_DIR,
        name="test_run",
        exist_ok=True,
        device='cpu',
        imgsz=640,
        conf=0.30,
        iou=0.5,
        task='obb'
    )

    pred_labels_dir = os.path.join(TEMP_SAVE_DIR, "test_run", "labels")
    txt_files = glob(os.path.join(pred_labels_dir, "*.txt"))

    for f in txt_files:
        shutil.copy(f, FINAL_LABELS_DIR)

    print(f"✅ 推理完成，txt 标签已复制到: {FINAL_LABELS_DIR}")

def calculate_angle(orig_labels_dir, labels3_dir, angle_dir):
    """Step 4: Calculate angles"""
    print("Step 4: Calculating angles")

    def calculate_centroid(points):
        n = len(points)
        cx = sum(p[0] for p in points) / n
        cy = sum(p[1] for p in points) / n
        return cx, cy

    def parse_label_file(filepath):
        with open(filepath, 'r') as f:
            lines = f.readlines()
        if not lines:
            return None
        parts = lines[0].strip().split()
        class_id = parts[0]
        coords = [float(c) for c in parts[1:]]
        points = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]
        centroid = calculate_centroid(points)
        return centroid, class_id

    os.makedirs(angle_dir, exist_ok=True)

    if not os.path.isdir(orig_labels_dir):
        return

    for filename in os.listdir(orig_labels_dir):
        if not filename.endswith('.txt'):
            continue

        orig_path = os.path.join(orig_labels_dir, filename)
        parsed = parse_label_file(orig_path)
        if parsed is None:
            continue
        c_orig, class_orig = parsed

        with open(orig_path, 'r') as f:
            parts = f.readline().strip().split()
        coords = [float(x) for x in parts[1:]]
        xs = coords[::2]
        ys = coords[1::2]
        left = min(xs)
        right = max(xs)
        upper = min(ys)
        lower = max(ys)

        candidate_path = os.path.join(labels3_dir, filename)
        if not os.path.exists(candidate_path):
            base = filename[:-4]
            found = None
            if os.path.isdir(labels3_dir):
                for f in os.listdir(labels3_dir):
                    if not f.lower().endswith('.txt'):
                        continue
                    if f == filename or f.startswith(base + '_'):
                        found = os.path.join(labels3_dir, f)
                        candidate_name = f
                        break
            if not found:
                continue
            candidate_path = found
            out_name = candidate_name
        else:
            out_name = filename

        parsed2 = parse_label_file(candidate_path)
        if parsed2 is None:
            continue
        c_crop, class_crop = parsed2
        if class_orig != class_crop:
            continue

        crop_w = right - left
        crop_h = lower - upper
        full_x = left + c_crop[0] * crop_w
        full_y = upper + c_crop[1] * crop_h

        dx = full_x - c_orig[0]
        dy = full_y - c_orig[1]
        angle = math.degrees(math.atan2(dy, dx))

        robot_rz = -angle - 225
        robot_rz = robot_rz % 360
        if robot_rz > 180:
            robot_rz = robot_rz - 360
        elif robot_rz < -180:
            robot_rz = robot_rz + 360

        with open(os.path.join(angle_dir, out_name), 'w') as f:
            f.write(f"{robot_rz}\n")

def process_pick():
    """Step 5: Process pick data"""
    print("Step 5: Processing pick data")

    def calculate_centroid(points):
        n = len(points)
        cx = sum(p[0] for p in points) / n
        cy = sum(p[1] for p in points) / n
        return cx, cy

    orig_labels_dir = os.path.join(BASE_DIR, "data", "images3", "orig_labels")
    if not os.path.isdir(orig_labels_dir) or not any(n.lower().endswith('.txt') for n in os.listdir(orig_labels_dir)):
        alt = os.path.join(BASE_DIR, "data", "images3", "labels")
        if os.path.isdir(alt):
            orig_labels_dir = alt

    angle_dir = os.path.join(BASE_DIR, "data", "angle")
    pick_dir = os.path.join(BASE_DIR, "pick")

    os.makedirs(pick_dir, exist_ok=True)

    for filename in os.listdir(orig_labels_dir):
        if not filename.endswith('.txt'):
            continue
        label_path = os.path.join(orig_labels_dir, filename)
        angle_path = os.path.join(angle_dir, filename)
        if not os.path.exists(angle_path):
            continue
        with open(angle_path, 'r') as f:
            angle = float(f.read().strip())

        with open(label_path, 'r') as f:
            lines = f.readlines()

        with open(os.path.join(pick_dir, filename), 'w') as f_out:
            for line in lines:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                class_id = parts[0]
                coords = [float(c) for c in parts[1:]]
                points = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]
                cx, cy = calculate_centroid(points)
                f_out.write(f"{cx:.6f} {cy:.6f} {angle:.6f}\n")

# Execute integrated steps
run_testseg()
crop_images_single_target("data/images", "data/labels", "data/images3")
run_testseg2()
calculate_angle(
    os.path.join(BASE_DIR, "data", "images3", "orig_labels"),
    os.path.join(BASE_DIR, "data", "images3", "labels3"),
    os.path.join(BASE_DIR, "data", "angle")
)
process_pick()

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

# 标定时的图像分辨率（需要手动设置或从配置文件读取）
CALIB_WIDTH = 3073   # ← 修改这里：标定时相机宽度
CALIB_HEIGHT = 2048  # ← 修改这里：标定时相机高度

def pixel_to_robot(u, v, H, current_w, current_h, calib_w, calib_h):
    """
    像素坐标转换为机器人坐标，支持分辨率适配

    参数：
    u, v: 当前图像的像素坐标
    H: 单应矩阵
    current_w, current_h: 当前图像分辨率
    calib_w, calib_h: 标定时图像分辨率
    """
    # 将当前分辨率的坐标缩放到标定时的分辨率
    scale_x = calib_w / current_w
    scale_y = calib_h / current_h

    u_calib = u * scale_x
    v_calib = v * scale_y

    p = np.array([u_calib, v_calib, 1.0], dtype=np.float64)
    pw = H @ p
    pw /= pw[2]
    return float(pw[0]), float(pw[1])

end_dir = "end"
os.makedirs(end_dir, exist_ok=True)

print(f"当前图像分辨率: {img_w}x{img_h}")
print(f"标定时分辨率: {CALIB_WIDTH}x{CALIB_HEIGHT}")

for file in files:
    if not file.endswith(".txt"):
        continue
    pixel_path = os.path.join(output_dir, file)
    end_path = os.path.join(end_dir, file)
    with open(pixel_path, "r") as f:
        line = f.readline().strip()
    x_px, y_px, angle = map(float, line.split())
    X, Y = pixel_to_robot(x_px, y_px, H, img_w, img_h, CALIB_WIDTH, CALIB_HEIGHT)
    with open(end_path, "w") as f:
        f.write(f"{X:.3f} {Y:.3f} {angle:.6f}\n")
    print(f"Converted: {file} -> Robot: ({X:.3f}, {Y:.3f}), Angle: {angle:.6f}")

print("All steps completed. Results in 'end' directory.")
