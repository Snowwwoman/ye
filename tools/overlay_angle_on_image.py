import os
import math
import cv2
import argparse
from datetime import datetime


def calculate_centroid(points):
    n = len(points)
    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n
    return cx, cy


def parse_label_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    if not lines:
        return None
    parts = lines[0].strip().split()
    class_id = parts[0]
    coords = [float(c) for c in parts[1:]]
    points = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]
    centroid = calculate_centroid(points)
    return centroid, class_id, points


def find_image_for_label(image_dir, label_filename):
    # Prefer an image whose stem matches the label stem (e.g. label: name_1.txt -> image: name_1.bmp)
    stem = label_filename[:-4]
    short_base = stem.split('_')[0]
    exts = ('.bmp', '.png', '.jpg', '.jpeg', '.tif', '.tiff')

    # 1) exact stem + ext
    for ext in exts:
        p = os.path.join(image_dir, stem + ext)
        if os.path.exists(p):
            return p

    # 2) any file starting with the full stem
    if os.path.isdir(image_dir):
        for f in os.listdir(image_dir):
            if f.lower().startswith(stem.lower()):
                return os.path.join(image_dir, f)

    # 3) fallback to short base (original image name)
    for ext in exts:
        p = os.path.join(image_dir, short_base + ext)
        if os.path.exists(p):
            return p
    if os.path.isdir(image_dir):
        for f in os.listdir(image_dir):
            if f.lower().startswith(short_base.lower()):
                return os.path.join(image_dir, f)
    return None


def compute_full_centroids(orig_path, crop_path):
    parsed = parse_label_file(orig_path)
    parsed2 = parse_label_file(crop_path)
    if parsed is None or parsed2 is None:
        return None
    c_orig, class_orig, pts_orig = parsed
    c_crop, class_crop, pts_crop = parsed2
    if class_orig != class_crop:
        return None

    xs = [p[0] for p in pts_orig]
    ys = [p[1] for p in pts_orig]
    left = min(xs)
    right = max(xs)
    upper = min(ys)
    lower = max(ys)
    crop_w = right - left
    crop_h = lower - upper

    full_x = left + c_crop[0] * crop_w
    full_y = upper + c_crop[1] * crop_h

    dx = full_x - c_orig[0]
    dy = full_y - c_orig[1]
    angle_orig = math.degrees(math.atan2(dy, dx))

    # display angle: x-axis positive, CCW positive (convert image coords where y down -> math y up)
    display_angle = math.degrees(math.atan2(-dy, dx))

    # robot transform kept same as existing pipeline
    robot_rz = -angle_orig - 235
    robot_rz = robot_rz % 360
    if robot_rz > 180:
        robot_rz = robot_rz - 360
    elif robot_rz < -180:
        robot_rz = robot_rz + 360

    return {
        'c_orig': c_orig,
        'c_full': (full_x, full_y),
        'display_angle': display_angle,
        'robot_rz': robot_rz,
        'pts_orig': pts_orig,
        'pts_crop': pts_crop,
    }


def overlay_and_save(image_path, data, out_path, scale_text=1.0):
    img = cv2.imread(image_path)
    if img is None:
        print('Failed to read image:', image_path)
        return False
    h, w = img.shape[:2]

    # convert normalized to pixels
    def to_px(p):
        x = int(round(p[0] * w))
        y = int(round(p[1] * h))
        return x, y

    orig_px = to_px(data['c_orig'])
    det_px = to_px(data['c_full'])

    # draw original polygon
    poly_pts = [(int(round(x * w)), int(round(y * h))) for x, y in data['pts_orig']]
    if len(poly_pts) >= 2:
        pts = poly_pts + [poly_pts[0]]
        for i in range(len(pts)-1):
            cv2.line(img, pts[i], pts[i+1], (0, 128, 255), 2)

    # draw centers
    cv2.circle(img, orig_px, 8, (255, 0, 0), -1)  # blue
    cv2.circle(img, det_px, 8, (0, 0, 255), -1)   # red

    # draw arrow from orig to det
    cv2.arrowedLine(img, orig_px, det_px, (0, 255, 0), 4, tipLength=0.03)

    # annotate angles and coords
    angle_text = f"{data['display_angle']:.2f}° (robot {data['robot_rz']:.2f}°)"
    # place text near midpoint
    mx = (orig_px[0] + det_px[0]) // 2
    my = (orig_px[1] + det_px[1]) // 2
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, angle_text, (mx+10, my-10), font, 1.0*scale_text, (0,0,0), 3, cv2.LINE_AA)
    cv2.putText(img, angle_text, (mx+10, my-10), font, 1.0*scale_text, (255,255,255), 1, cv2.LINE_AA)

    # small labels for points
    cv2.putText(img, 'orig', (orig_px[0]+10, orig_px[1]+10), font, 0.8*scale_text, (255,255,255), 2, cv2.LINE_AA)
    cv2.putText(img, 'det', (det_px[0]+10, det_px[1]+10), font, 0.8*scale_text, (255,255,255), 2, cv2.LINE_AA)

    # draw X axis indicator (image-right is positive X). Placed near top-left as a reference.
    axis_y = int(round(h * 0.06))
    axis_x0 = int(round(w * 0.06))
    axis_x1 = int(round(w * 0.26))
    cv2.arrowedLine(img, (axis_x0, axis_y), (axis_x1, axis_y), (0, 255, 255), 3, tipLength=0.05)
    cv2.putText(img, 'X → (0°)', (axis_x1 + 8, axis_y + 6), font, 0.7 * scale_text, (255, 255, 255), 2, cv2.LINE_AA)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cv2.imwrite(out_path, img)
    return True


def find_match(labels3_dir, filename):
    candidate = os.path.join(labels3_dir, filename)
    if os.path.exists(candidate):
        return candidate, filename
    base = filename[:-4]
    if os.path.isdir(labels3_dir):
        for f in os.listdir(labels3_dir):
            if not f.lower().endswith('.txt'):
                continue
            if f == filename or f.startswith(base + '_'):
                return os.path.join(labels3_dir, f), f
    return None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--orig-dir', default=os.path.join('vision','project2','data','images3','labels'))
    parser.add_argument('--labels3-dir', default=os.path.join('vision','project2','data','images3','labels3'))
    # Default image-dir: cropped images folder
    parser.add_argument('--image-dir', default=os.path.join('vision','project2','data','images3','images'))
    # Default out-dir: only save overlays on crops
    parser.add_argument('--out-dir', default=os.path.join('tools','visualizations_on_crops'))
    parser.add_argument('--name')
    args = parser.parse_args()

    if args.name:
        files = [args.name]
    else:
        if not os.path.isdir(args.orig_dir):
            print('orig-dir missing:', args.orig_dir)
            return
        files = [f for f in os.listdir(args.orig_dir) if f.lower().endswith('.txt')]

    for fname in files:
        orig_path = os.path.join(args.orig_dir, fname)
        match_path, out_name = find_match(args.labels3_dir, fname)
        if not match_path:
            print('no match for', fname)
            continue
        data = compute_full_centroids(orig_path, match_path)
        if data is None:
            print('compute failed for', fname)
            continue
        img_path = find_image_for_label(args.image_dir, fname)
        if not img_path:
            print('image not found for', fname)
            continue
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_path = os.path.join(args.out_dir, f"overlay_{out_name[:-4]}_{stamp}.jpg")
        ok = overlay_and_save(img_path, data, out_path)
        if ok:
            print('Saved overlay:', out_path)
        else:
            print('Failed to save overlay for', fname)

if __name__ == '__main__':
    main()
