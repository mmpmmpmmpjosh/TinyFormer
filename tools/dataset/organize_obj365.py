import json
import os
import shutil
import argparse
from pathlib import Path

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Organize Objects365 dataset into v1/v2 structure')
    parser.add_argument(
        '--base_dir',
        type=str,
        default='datasets/Objects365',
        help='Base directory of the dataset'
    )
    return parser.parse_args()

def organize_images_and_annotations(base_dir):
    """Organize images and annotation files into the specified structure"""
    train_dir = os.path.join(base_dir, 'train')
    val_dir = os.path.join(base_dir, 'val')
    
    # Define annotation paths
    train_ann_file = os.path.join(train_dir, 'zhiyuan_objv2_train.json')
    val_ann_file = os.path.join(val_dir, 'zhiyuan_objv2_val.json')
    
    # Load annotation files
    print('Loading training annotations...')
    with open(train_ann_file, 'r') as f:
        train_annotations = json.load(f)
        
    print('Loading validation annotations...')
    with open(val_ann_file, 'r') as f:
        val_annotations = json.load(f)
    
    # Create images directories
    train_images_dir = os.path.join(train_dir, 'images')
    val_images_dir = os.path.join(val_dir, 'images')
    os.makedirs(train_images_dir, exist_ok=True)
    os.makedirs(val_images_dir, exist_ok=True)
    
    # Process both train and val datasets
    for dataset_type, annotations, images_dir in [
        ('train', train_annotations, train_images_dir),
        ('val', val_annotations, val_images_dir)
    ]:
        print(f'Organizing {dataset_type} dataset...')
        
        # Create version-specific directories
        v1_dir = os.path.join(images_dir, 'v1')
        v2_dir = os.path.join(images_dir, 'v2')
        os.makedirs(v1_dir, exist_ok=True)
        os.makedirs(v2_dir, exist_ok=True)
        
        # Group images by patch
        patch_to_images = {}
        for img in annotations['images']:
            parts = img['file_name'].split('/')
            patch_name = parts[-2]  # Extract patch name (e.g., 'patch8')
            if patch_name not in patch_to_images:
                patch_to_images[patch_name] = []
            patch_to_images[patch_name].append(img)
        
        # Sort patches into v1 or v2
        for patch_name, images in patch_to_images.items():
            # Check if patch belongs to v1 or v2 based on file_name
            is_v1 = any('v1' in img['file_name'] for img in images)
            target_dir = v1_dir if is_v1 else v2_dir
            
            # Create patch directory under v1 or v2
            patch_target_dir = os.path.join(target_dir, patch_name)
            os.makedirs(patch_target_dir, exist_ok=True)
            
            # Move images to the new location
            for img in images:
                img_name = img['file_name'].split('/')[-1]
                src_path = os.path.join(base_dir, dataset_type, patch_name, img_name)
                dst_path = os.path.join(patch_target_dir, img_name)
                
                if os.path.exists(src_path):
                    shutil.move(src_path, dst_path)
                    print(f'Moved: {src_path} -> {dst_path}')
                else:
                    print(f'Warning: Source not found: {src_path}')
        
        # Remove empty patch directories
        for patch_name in patch_to_images:
            patch_dir = os.path.join(base_dir, dataset_type, patch_name)
            if os.path.exists(patch_dir) and not os.listdir(patch_dir):
                shutil.rmtree(patch_dir)
                print(f'Removed empty directory: {patch_dir}')

def main():
    """Main execution block"""
    args = parse_arguments()
    base_dir = args.base_dir
    
    # Verify directory existence
    if not os.path.exists(os.path.join(base_dir, 'train')):
        print(f'Error: Training directory {base_dir}/train does not exist')
        return
    if not os.path.exists(os.path.join(base_dir, 'val')):
        print(f'Error: Validation directory {base_dir}/val does not exist')
        return
    
    organize_images_and_annotations(base_dir)
    print('Dataset organization completed.')

if __name__ == '__main__':
    main()