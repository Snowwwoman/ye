from ultralytics import YOLO
import os
import shutil
from glob import glob
from pathlib import Path

# 定义 current_dir
current_dir = Path(__file__).parent
#使用相对路径
MODEL_PATH = current_dir / "train_seg" / "run_20251231_113438" / "weights" / "best.pt"
IMAGES_DIR = current_dir / "images" / "test"
TEMP_SAVE_DIR=current_dir/"test_seg" #临时保存预测绘结果
FINAL_LABELS_DIR = current_dir / "labels"/ "test" # E标标签目录
os.makedirs(TEMP_SAVE_DIR, exist_ok=True)
os.makedirs(FINAL_LABELS_DIR, exist_ok=True)

# 加载模型
model = YOLO(MODEL_PATH)

# 批量推理
results = model.predict(
    source=IMAGES_DIR,
    save=True,
    save_txt=True,
    project=TEMP_SAVE_DIR,
    name="test_run",
    exist_ok=True,
    device='cpu',
    imgsz=640,
    conf=0.50,
    iou=0.5,
)

# 推理结果 txt 文件所在目录
pred_labels_dir = os.path.join(TEMP_SAVE_DIR, "test_run", "labels")
txt_files = glob(os.path.join(pred_labels_dir, "*.txt"))

# 复制到指定目录
for f in txt_files:
    shutil.copy(f, FINAL_LABELS_DIR)

print(f"✅ 推理完成，txt 标签已复制到: {FINAL_LABELS_DIR}")
