import cv2
import numpy as np
import os

# =========================
# 配置（使用脚本目录）
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CALIB_IMAGE = os.path.join(BASE_DIR, "Image_20251216142353118.bmp")  # 标定板图片路径
PATTERN_SIZE = (4, 4)  # 内角点数量 (行,列)
VISUALIZE = True  # 是否保存角点可视化图片
OUT_VIS = os.path.join(BASE_DIR, "calib_corners_vis_numbered.jpg")

# =========================
# 1. 读取标定板图像
# =========================
img = cv2.imread(CALIB_IMAGE)
if img is None:
    raise RuntimeError("标定板图像读取失败")
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# =========================
# 2. 查找棋盘角点
# =========================
found, corners = cv2.findChessboardCorners(
    gray,
    PATTERN_SIZE,
    flags=cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
)
if not found:
    raise RuntimeError("未检测到棋盘角点")

# 亚像素优化
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
corners_subpix = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

# =========================
# 3. 选取九个点（左上3x3区域，行优先）
# =========================
nine_idx = [0, 1, 2,
            4, 5, 6,
            8, 9, 10]
img_points = np.array([corners_subpix[i][0] for i in nine_idx], dtype=np.float32)

# =========================
# 4. 可视化九个点顺序
# =========================
vis_img = img.copy()
for idx, pt in enumerate(img_points):
    x, y = int(pt[0]), int(pt[1])
    cv2.circle(vis_img, (x, y), 5, (0, 0, 255), -1)
    cv2.putText(vis_img, str(idx+1), (x+5, y-5), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (0, 255, 0), 2)

if VISUALIZE:
    cv2.imwrite(OUT_VIS, vis_img)
    print("九个标定点顺序可视化已保存:", OUT_VIS)

# =========================
# 5. 手动输入九个机器人坐标 (mm)
# =========================
robot_points = []
print("请输入对应九个机器人坐标 (X Y) ，单位 mm，按编号顺序 1~9：")
for i in range(9):
    x, y = input(f"第{i+1}点: ").split()
    robot_points.append([float(x), float(y)])
robot_points = np.array(robot_points, dtype=np.float32)

# =========================
# 6. 计算单应矩阵 H
# =========================
H, _ = cv2.findHomography(img_points, robot_points)
print("单应矩阵 H:\n", H)

# 保存单应矩阵
H_SAVE_PATH = os.path.join(BASE_DIR, "pixel_to_robot_H.npy")
np.save(H_SAVE_PATH, H)
print("单应矩阵已保存到:", H_SAVE_PATH)

# =========================
# 7. 像素坐标 -> 机器人坐标函数
# =========================
def pixel_to_robot(u, v, H):
    p = np.array([u, v, 1.0])
    pw = H @ p
    pw /= pw[2]
    return pw[0], pw[1]

