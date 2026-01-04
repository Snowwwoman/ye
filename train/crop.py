import os
import shutil
from PIL import Image
import argparse
from pathlib import Path

# ============ 路径配置部分 ============
# 在这里设置您的默认路径
DEFAULT_PATHS = {
    "source_dir": r"C:\Users\Administrator\Desktop\train\dataset10",  # 源数据集目录
    "dest_dir": r"C:\Users\Administrator\Desktop\train\dataset10_cropped2",  # 裁剪后目录
}

def crop_images_single_target(source_dir, labels_dir, dest_dir, save_adjusted_coords=True, adjusted_suffix='_adjusted', separate_original=True):
    """
    将图片裁剪为单目标图片
    """
    if os.path.exists(dest_dir):
        print(f"删除已存在的目标目录: {dest_dir}")
        shutil.rmtree(dest_dir)
    
    subfolders = ['train', 'val', 'test']
    
    total_images = 0
    total_objects = 0
    
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

        # 检查源目录是否存在
        if not os.path.exists(img_sub):
            print(f"警告: 图片目录不存在: {img_sub}")
            continue
        
        if not os.path.exists(lbl_sub):
            print(f"警告: 标签目录不存在: {lbl_sub}")
            continue

        folder_images = 0
        folder_objects = 0
        
        for root, dirs, files in os.walk(img_sub):
            for file in files:
                if not file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    continue

                base = file[:-4]
                img_path = os.path.join(root, file)
                txt_path = os.path.join(lbl_sub, base + '.txt')

                if not os.path.exists(txt_path):
                    print(f"警告: 标签文件不存在: {txt_path}")
                    continue

                try:
                    img = Image.open(img_path)
                    w, h = img.size
                    total_images += 1

                    with open(txt_path, 'r') as f:
                        lines = f.readlines()

                    for i, line in enumerate(lines):
                        parts = line.strip().split()
                        if len(parts) < 5:  # 至少类 + 4个坐标（矩形）
                            continue  # 非法行

                        class_id = parts[0]
                        coords = parts[1:]
                        
                        # 检查坐标格式
                        valid_coords = True
                        for coord in coords:
                            # 更严格的坐标格式检查
                            try:
                                float(coord)
                            except ValueError:
                                valid_coords = False
                                break
                        
                        if not valid_coords or len(coords) % 2 != 0:
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

                        if left >= right or upper >= lower:
                            print(f"警告: 无效边界框: {img_path} 第{i}个目标")
                            continue

                        # 裁剪单目标图片
                        crop_img = img.crop((left, upper, right, lower))
                        crop_name = f'{base}_{i}.jpg'
                        crop_save_path = os.path.join(out_img_sub, crop_name)
                        crop_img.save(crop_save_path)

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

                        folder_objects += 1
                        total_objects += 1
                    
                    folder_images += 1
                    
                except Exception as e:
                    print(f"处理图片 {img_path} 时出错: {str(e)}")
                    continue
        
        print(f"{sub} 文件夹: 处理 {folder_images} 张图片, 裁剪出 {folder_objects} 个目标")
    
    print("=" * 50)
    print(f"裁剪完成!")
    print(f"总计: {total_images} 张原始图片")
    print(f"总计: {total_objects} 个裁剪目标")
    print(f"输出目录: {dest_dir}")

def create_dataset_yaml(dataset_dir, class_names=None):
    """
    创建YOLO格式的数据集配置文件
    """
    if class_names is None:
        class_names = {0: 'object'}
    
    yaml_content = f"""path: {dataset_dir}
train: images/train
val: images/val
test: images/test
nc: {len(class_names)}
names: {class_names}
"""
    
    yaml_path = os.path.join(dataset_dir, 'data.yaml')
    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content)
    
    print(f"已创建数据集配置文件: {yaml_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Crop images into single targets.')
    
    # 使用默认路径作为默认值
    parser.add_argument('--source_dir', type=str, default=DEFAULT_PATHS["source_dir"],
                       help=f'Source dataset directory (default: {DEFAULT_PATHS["source_dir"]})')
    
    parser.add_argument('--labels_dir', type=str, default=None,
                       help='Labels directory inside source_dir, default source_dir/labels')
    
    parser.add_argument('--dest_dir', type=str, default=DEFAULT_PATHS["dest_dir"],
                       help=f'Destination dataset directory (default: {DEFAULT_PATHS["dest_dir"]})')
    
    parser.add_argument('--create_yaml', action='store_true',
                       help='Create YOLO dataset YAML file after cropping')
    
    args = parser.parse_args()
    
    # 如果没有指定标签目录，使用默认位置
    if args.labels_dir is None:
        args.labels_dir = os.path.join(args.source_dir, 'labels')
    
    # 显示路径信息
    print("=" * 50)
    print("裁剪配置:")
    print(f"源数据集目录: {args.source_dir}")
    print(f"标签目录: {args.labels_dir}")
    print(f"输出目录: {args.dest_dir}")
    print("=" * 50)
    
    # 执行裁剪
    crop_images_single_target(
        source_dir=args.source_dir,
        labels_dir=args.labels_dir,
        dest_dir=args.dest_dir
    )
    
    # 如果需要创建YAML文件
    if args.create_yaml:
        create_dataset_yaml(args.dest_dir)