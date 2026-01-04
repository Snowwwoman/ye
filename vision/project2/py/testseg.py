
from ultralytics import YOLO
import os
import shutil
from glob import glob
import sys

# 路径配置（基于脚本目录）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "best.pt")
IMAGES_DIR = os.path.join(BASE_DIR, "data", "images")
TEMP_SAVE_DIR = os.path.join(BASE_DIR, "data")  # 临时保存预测结果
FINAL_LABELS_DIR = os.path.join(BASE_DIR, "data", "labels")  # 目标标签目录

os.makedirs(TEMP_SAVE_DIR, exist_ok=True)
os.makedirs(FINAL_LABELS_DIR, exist_ok=True)

# 加载模型
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
    sys.exit(0)

print(f"🔎 使用最新图片进行推理: {newest}")

# 对单张图片进行推理
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

# 推理结果 txt 文件所在目录
pred_labels_dir = os.path.join(TEMP_SAVE_DIR, "test_run", "labels")
# 预测的标签文件名与图片同名（去扩展名）
base = os.path.splitext(os.path.basename(newest))[0]
pred_txt = os.path.join(pred_labels_dir, base + ".txt")

if os.path.exists(pred_txt):
    shutil.copy(pred_txt, FINAL_LABELS_DIR)
    print(f"✅ 推理完成，标签已复制到: {FINAL_LABELS_DIR}\n-> {pred_txt}")
else:
    print(f"⚠️ 未找到预测的 txt 文件: {pred_txt}")
