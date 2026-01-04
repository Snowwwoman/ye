
from ultralytics import YOLO
import os
import time
import torch    
from pathlib import Path

# -----------------------
# 基本路径
# 定义 current_dir
current_dir = Path(__file__).parent
# -----------------------
#使用相对路径
DATA_YAML = current_dir / "data10.yaml"
MODEL_PATH="yolov8n-seg.pt"#这通常会在当前目录或YOLO自动下载
PROJECT_DIR = current_dir / "train_seg"

# 若不存在则自动创建
os.makedirs(PROJECT_DIR, exist_ok=True)

# -----------------------
# 自动创建唯一 run 名字（时间戳）
# -----------------------
run_name = "run_" + time.strftime("%Y%m%d_%H%M%S")

print("📁 本次训练文件夹:", os.path.join(PROJECT_DIR, run_name))

# -----------------------
# 加载模型
# -----------------------
model = YOLO(MODEL_PATH)

# -----------------------
# 训练
# -----------------------

model.train(
    data=DATA_YAML,
    epochs= 50,
    imgsz=640,
    batch=10,
    project=PROJECT_DIR,   # 大目录
    name=run_name,         # 每次唯一的子目录
    exist_ok=False,        # ⭐ 必须 False，这样不会覆盖也不会复用
    device='cpu',
    task='seg',
    lr0=0.05
)

# -----------------------
# 输出完成信息
# -----------------------
print("✅ 训练完成，结果保存在:")
print(os.path.join(PROJECT_DIR, run_name))
