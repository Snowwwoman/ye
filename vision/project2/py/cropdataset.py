import os
from PIL import Image

def crop_images_single_target(
    source_dir,
    labels_dir,
    dest_dir,
    save_adjusted_coords=True,
    adjusted_suffix='_adjusted',
    separate_original=True
):
    if os.path.exists(dest_dir):
        import shutil
        shutil.rmtree(dest_dir)

    img_sub = source_dir
    lbl_sub = labels_dir

    out_img_sub = os.path.join(dest_dir, 'images')
    out_lbl_sub = os.path.join(dest_dir, 'labels')
    orig_lbl_sub = os.path.join(dest_dir, 'orig_labels') if separate_original else out_lbl_sub

    os.makedirs(out_img_sub, exist_ok=True)
    os.makedirs(out_lbl_sub, exist_ok=True)
    if separate_original:
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

                if save_adjusted_coords:
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

import argparse
import os

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Crop images into single targets.')
    parser.add_argument('--source_dir', type=str, required=True, help='Source images directory (required)')
    parser.add_argument('--labels_dir', type=str, required=True, help='Labels directory (required)')
    parser.add_argument('--dest_dir', type=str, required=True, help='Destination directory (required)')

    args = parser.parse_args()

    crop_images_single_target(
        source_dir=args.source_dir,
        labels_dir=args.labels_dir,
        dest_dir=args.dest_dir
    )
