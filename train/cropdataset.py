import os
from PIL import Image

def crop_images_single_target(source_dir, labels_dir, dest_dir, save_adjusted_coords=True, adjusted_suffix='_adjusted', separate_original=True):
    if os.path.exists(dest_dir):
        import shutil
        shutil.rmtree(dest_dir)
    subfolders = ['train', 'val', 'test']
    for sub in subfolders:
        img_sub = os.path.join(source_dir, 'images', sub)
        lbl_sub = os.path.join(labels_dir, sub)
        out_img_sub = os.path.join(dest_dir, 'images', sub)
        out_lbl_sub = os.path.join(dest_dir, 'mlabel', sub)
        if separate_original:
            orig_lbl_sub = os.path.join(dest_dir, 'orig_labels', sub)  # 另起文件夹存放原标签
        else:
            orig_lbl_sub = out_lbl_sub

        os.makedirs(out_img_sub, exist_ok=True)
        os.makedirs(out_lbl_sub, exist_ok=True)
        if separate_original:
            os.makedirs(orig_lbl_sub, exist_ok=True)

        for root, dirs, files in os.walk(img_sub):
            for file in files:
                if not file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    continue

                base = file[:-4]
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
                    if len(parts) < 5:  # 至少类 + 4个坐标（矩形）
                        continue  # 非法行

                    class_id = parts[0]
                    coords = parts[1:]
                    if len(coords) % 2 != 0 or not all(c.replace('.', '', 1).replace('-', '', 1).isdigit() for c in coords):
                        continue

                    coords_float = [float(c) for c in coords]
                    xs = coords_float[::2]
                    ys = coords_float[1::2]

                    min_x = min(xs)
                    max_x = max(xs)
                    min_y = min(ys)
                    max_y = max(ys)

                    left = int(min_x * w)
                    right = int(max_x * w)
                    upper = int(min_y * h)
                    lower = int(max_y * h)

                    if left >= right or upper >= lower or max_x <= min_x or max_y <= min_y:
                        continue  # 无效框

                    # 裁剪单目标图片
                    crop_img = img.crop((left, upper, right, lower))
                    crop_name = f'{base}_{i}.jpg'
                    crop_img.save(os.path.join(out_img_sub, crop_name))

                    # 保存原有相对坐标 到 orig_labels
                    with open(os.path.join(orig_lbl_sub, crop_name[:-4] + '.txt'), 'w') as f2:
                        f2.write(line)

                    if save_adjusted_coords:
                        # 保存裁剪后目标在图片中的坐标（调整后） 到 labels
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

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Crop images into single targets.')
    # TODO: 每次运行前修改下面的 source_dir 和 dest_dir为你要处理的文件夹
    parser.add_argument('--source_dir', type=str, required=True, help='Source dataset directory (required)')  # e.g. 'dataset5seg' or 'dataset10'
    parser.add_argument('--labels_dir', type=str, default=None, help='Labels directory inside source_dir, default source_dir/labels')
    parser.add_argument('--dest_dir', type=str, required=True, help='Destination dataset directory (required)')  # e.g. 'dataset5seg01' or 'dataset10_cropped'

    args = parser.parse_args()
    if args.labels_dir is None:
        args.labels_dir = os.path.join(args.source_dir, 'labels')

    crop_images_single_target(
        source_dir=args.source_dir,
        labels_dir=args.labels_dir,
        dest_dir=args.dest_dir
    )
