import os
import math

def calculate_centroid(points):
    n = len(points)
    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n
    return cx, cy

def process_orig_labels(orig_labels_dir, angle_dir, pick_dir):
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

if __name__ == '__main__':
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    orig_labels_dir = os.path.join(BASE_DIR, "data", "images3", "orig_labels")
    # fallback: if orig_labels doesn't exist or is empty, use data/images3/labels
    if not os.path.isdir(orig_labels_dir) or not any(n.lower().endswith('.txt') for n in os.listdir(orig_labels_dir)):
        alt = os.path.join(BASE_DIR, "data", "images3", "labels")
        if os.path.isdir(alt):
            orig_labels_dir = alt
    angle_dir = os.path.join(BASE_DIR, "data", "angle")
    pick_dir = os.path.join(BASE_DIR, "pick")
    process_orig_labels(orig_labels_dir, angle_dir, pick_dir)
    print("Pick data calculated and saved.")
