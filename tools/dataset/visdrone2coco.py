import os
import json
import glob
from PIL import Image

def visdrone_to_coco(txt_dir, img_dir, json_file):
    # Standard 10 detection classes for VisDrone (excluding 'ignored' and 'others')
    # The order here corresponds to the converted COCO category_id (0 ~ 9)
    VISDRONE_CLASSES = [
        "pedestrian", "people", "bicycle", "car", "van",
        "truck", "tricycle", "awning-tricycle", "bus", "motor"
    ]

    coco_data = {
        "images": [],
        "annotations": [],
        "categories": [{"id": i, "name": cls} for i, cls in enumerate(VISDRONE_CLASSES)]
    }

    ann_id = 1
    img_id = 1

    txt_files = glob.glob(os.path.join(txt_dir, '*.txt'))
    if not txt_files:
        print(f"No .txt files found in {txt_dir}!")
        return

    for txt_file in txt_files:
        base_name = os.path.basename(txt_file)
        # VisDrone images are typically .jpg
        img_name = base_name.replace('.txt', '.jpg') 
        img_path = os.path.join(img_dir, img_name)

        if not os.path.exists(img_path):
            print(f"Warning: Corresponding image {img_path} not found. Skipping.")
            continue

        try:
            with Image.open(img_path) as img:
                img_width, img_height = img.size
        except Exception as e:
            print(f"Failed to read image {img_path}: {e}")
            continue

        coco_data["images"].append({
            "id": img_id,
            "file_name": img_name,
            "width": img_width,
            "height": img_height
        })

        with open(txt_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # VisDrone format: <bbox_left>,<bbox_top>,<bbox_width>,<bbox_height>,<score>,<object_category>,<truncation>,<occlusion>
            parts = line.split(',')
            if len(parts) >= 6:
                x_min = float(parts[0])
                y_min = float(parts[1])
                width = float(parts[2])
                height = float(parts[3])
                score = int(parts[4])
                category = int(parts[5])

                # Filtering conditions:
                # 1. score == 0 usually represents ignored regions
                # 2. category == 0 (ignored regions) or 11 (others) are typically excluded from detection training
                if score == 0 or category == 0 or category == 11:
                    continue
                
                # Map VisDrone classes (1-10) to COCO classes (0-9)
                coco_class_id = category - 1

                coco_data["annotations"].append({
                    "id": ann_id,
                    "image_id": img_id,
                    "category_id": coco_class_id, 
                    "bbox": [x_min, y_min, width, height],
                    "area": width * height,
                    "iscrowd": 0,
                    "segmentation": [] 
                })
                ann_id += 1

        img_id += 1

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(coco_data, f, ensure_ascii=False, indent=4)

    print(f"VisDrone conversion completed!")
    print(f"Processed {img_id - 1} images, generated {ann_id - 1} valid bounding boxes (filtered ignored/others).")
    print(f"Output file: {json_file}")


if __name__ == "__main__":
    # Define paths for annotations, images, and output JSON
    TXT_FOLDER = 'VisDrone2019-DET-val/annotations'   
    IMG_FOLDER = 'VisDrone2019-DET-val/images'   
    OUTPUT_JSON = 'VisDrone2019-DET-val/val.json' 

    visdrone_to_coco(TXT_FOLDER, IMG_FOLDER, OUTPUT_JSON)