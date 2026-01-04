import os
import math

def calculate_centroid(points):
    # points is list of (x, y) tuples
    n = len(points)
    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n
    return cx, cy

def parse_label_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    if not lines:
        return None
    # Assume first line has the polygon
    parts = lines[0].strip().split()
    class_id = parts[0]
    coords = [float(c) for c in parts[1:]]
    # Group into (x,y)
    points = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]
    centroid = calculate_centroid(points)
    return centroid, class_id

def calculate_angle(orig_labels_dir, labels3_dir, angle_dir):
    os.makedirs(angle_dir, exist_ok=True)

    if not os.path.isdir(orig_labels_dir):
        return

    # For each crop's original label (contains original-image normalized coords and crop bbox),
    # find matching detection in labels3_dir (which is normalized inside the crop). Convert the
    # crop-local centroid back to full-image normalized coords using the crop bbox, then compute
    # the angle between the original centroid and the detected centroid in full-image coords.
    for filename in os.listdir(orig_labels_dir):
        if not filename.endswith('.txt'):
            continue

        orig_path = os.path.join(orig_labels_dir, filename)
        parsed = parse_label_file(orig_path)
        if parsed is None:
            continue
        c_orig, class_orig = parsed

        # also compute crop bbox from orig label coordinates (min/max of the polygon)
        with open(orig_path, 'r') as f:
            parts = f.readline().strip().split()
        coords = [float(x) for x in parts[1:]]
        xs = coords[::2]
        ys = coords[1::2]
        left = min(xs)
        right = max(xs)
        upper = min(ys)
        lower = max(ys)

        # find corresponding detection file in labels3_dir
        candidate_path = os.path.join(labels3_dir, filename)
        if not os.path.exists(candidate_path):
            # try variants (some tools may produce names without the exact suffix)
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

        # c_crop is centroid normalized inside the crop; map to full-image normalized coords
        crop_w = right - left
        crop_h = lower - upper
        full_x = left + c_crop[0] * crop_w
        full_y = upper + c_crop[1] * crop_h

        dx = full_x - c_orig[0]
        dy = full_y - c_orig[1]
        angle = math.degrees(math.atan2(dy, dx))

        # convert to robot RZ using same transform as tools/visualize_angle.py
        robot_rz = -angle - 225
        robot_rz = robot_rz % 360
        if robot_rz > 180:
            robot_rz = robot_rz - 360
        elif robot_rz < -180:
            robot_rz = robot_rz + 360

        with open(os.path.join(angle_dir, out_name), 'w') as f:
            f.write(f"{robot_rz}\n")

if __name__ == '__main__':
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # BASE_DIR currently points to .../project2/data, so go up one level
    PROJECT_DIR = os.path.dirname(BASE_DIR)
    orig_labels_dir = os.path.join(PROJECT_DIR, "data", "images3", "orig_labels")
    labels3_dir = os.path.join(PROJECT_DIR, "data", "images3", "labels3")
    angle_dir = os.path.join(PROJECT_DIR, "data", "angle")
    if not os.path.isdir(orig_labels_dir):
        print(f"orig_labels_dir not found: {orig_labels_dir}")
    else:
        calculate_angle(orig_labels_dir, labels3_dir, angle_dir)
    print("Angles calculated and saved.")
