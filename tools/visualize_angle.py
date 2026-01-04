import os
import math
import argparse
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


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


def compute_robot_angle_and_full_centroids(orig_path, crop_path):
    parsed = parse_label_file(orig_path)
    parsed2 = parse_label_file(crop_path)
    if parsed is None or parsed2 is None:
        return None
    c_orig, class_orig, pts_orig = parsed
    c_crop, class_crop, pts_crop = parsed2
    if class_orig != class_crop:
        return None

    # compute crop bbox from orig polygon coords (normalized full-image coords)
    coords = []
    for p in pts_orig:
        coords.extend(p)
    xs = coords[::2]
    ys = coords[1::2]
    left = min(xs)
    right = max(xs)
    upper = min(ys)
    lower = max(ys)
    crop_w = right - left
    crop_h = lower - upper

    # map crop-local centroid (normalized in crop) to full-image normalized coords
    full_x = left + c_crop[0] * crop_w
    full_y = upper + c_crop[1] * crop_h

    dx = full_x - c_orig[0]
    dy = full_y - c_orig[1]

    # angle computed in existing pipeline (image coords where y grows down):
    angle_orig = math.degrees(math.atan2(dy, dx))

    # same robot transform as existing pipeline
    robot_rz = -angle_orig - 235
    robot_rz = robot_rz % 360
    if robot_rz > 180:
        robot_rz = robot_rz - 360
    elif robot_rz < -180:
        robot_rz = robot_rz + 360

    # For visualization, use math coordinate system: x positive right, y positive up
    # image normalized y increases down, so flip dy for math angle
    dy_math = -dy
    display_angle = math.degrees(math.atan2(dy_math, dx))

    return {
        'c_orig': c_orig,
        'c_full': (full_x, full_y),
        'angle_orig': angle_orig,
        'display_angle': display_angle,
        'robot_rz': robot_rz,
        'pts_orig': pts_orig,
        'pts_crop': pts_crop,
    }


def draw_visualization(data, out_path, title=None):
    # plot normalized coordinates in [0,1] square
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect('equal')

    # convert to math coords (y up) for plotting: image y is down, so y_plot = 1 - y
    def to_plot(p):
        return (p[0], 1 - p[1])

    c_orig = to_plot(data['c_orig'])
    c_full = to_plot(data['c_full'])

    # draw original polygon
    poly_orig = [to_plot(p) for p in data['pts_orig']] + [to_plot(data['pts_orig'][0])]
    xs = [p[0] for p in poly_orig]
    ys = [p[1] for p in poly_orig]
    ax.plot(xs, ys, '-k', linewidth=1, label='orig polygon')

    # draw crop-local polygon (not positioned in full image) as small inset near its centroid
    # (optional) skip drawing crop polygon in full-image coords since we don't have explicit bbox corners here

    # draw centers
    ax.scatter([c_orig[0]], [c_orig[1]], c='blue', s=60, label='orig centroid')
    ax.scatter([c_full[0]], [c_full[1]], c='red', s=60, label='detected centroid')

    # draw arrow from orig to detected (in math coords)
    ax.annotate('', xy=c_full, xytext=c_orig, arrowprops=dict(arrowstyle='->', color='green', lw=2))

    # annotate angle (display_angle: x-axis positive, CCW positive)
    angle_text = f"Angle: {data['display_angle']:.2f}°\n(robot_rz: {data['robot_rz']:.2f}°)"
    midx = (c_orig[0] + c_full[0]) / 2
    midy = (c_orig[1] + c_full[1]) / 2
    ax.text(midx, midy, angle_text, color='black', fontsize=10, ha='center', va='bottom', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    ax.set_xlabel('Normalized X (right positive)')
    ax.set_ylabel('Normalized Y (up positive)')
    if title:
        ax.set_title(title)
    ax.legend(loc='upper right')
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


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
    parser = argparse.ArgumentParser(description='Visualize centroids and angle between orig label and labels3 detection')
    parser.add_argument('--orig-dir', default=os.path.join('vision', 'project2', 'data', 'images3', 'labels'), help='Original labels dir (normalized in full image)')
    parser.add_argument('--labels3-dir', default=os.path.join('vision', 'project2', 'data', 'images3', 'labels3'), help='labels3 detected in crops')
    parser.add_argument('--out-dir', default=os.path.join('tools', 'visualizations'), help='Output images folder')
    parser.add_argument('--name', help='Specific label filename to visualize (e.g. Image_..._0.txt). If omitted, process all matches found in orig-dir')
    args = parser.parse_args()

    orig_dir = args.orig_dir
    labels3_dir = args.labels3_dir
    out_dir = args.out_dir

    if args.name:
        files = [args.name]
    else:
        if not os.path.isdir(orig_dir):
            print('orig-dir not found:', orig_dir)
            return
        files = [f for f in os.listdir(orig_dir) if f.lower().endswith('.txt')]

    for fname in files:
        orig_path = os.path.join(orig_dir, fname)
        if not os.path.exists(orig_path):
            print('orig file missing:', orig_path)
            continue
        match_path, out_name = find_match(labels3_dir, fname)
        if not match_path:
            print('no matching labels3 for', fname)
            continue
        result = compute_robot_angle_and_full_centroids(orig_path, match_path)
        if result is None:
            print('failed to compute for', fname)
            continue
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_path = os.path.join(out_dir, f"vis_{out_name[:-4]}_{stamp}.png")
        title = f"{out_name} | angle={result['display_angle']:.2f}°"
        draw_visualization(result, out_path, title=title)
        print('Saved visualization:', out_path)


if __name__ == '__main__':
    main()
