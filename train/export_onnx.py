from ultralytics import YOLO

# 1. 加载模型
model = YOLO(r"D:\EagleGrab\dataset5seg01\train_seg\run_20251211_093307\weights\best.pt")

# 2. 导出为 ONNX
model.export(
    format='onnx',
    imgsz=(640, 640),  # v8.1 必须写成 tuple
    opset=12,          # v8.1 推荐 opset=12，兼容性最好
)
