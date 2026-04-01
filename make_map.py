import os
import json

# Base directory for images (your GitHub images folder)
IMAGE_BASE = r"C:\Users\Mikew0911\Desktop\ggen_db_images\images"

# Output file
OUTPUT_FILE = "image_index.json"

def build_image_index(base_path):
    """
    Scan all image folders and create an index mapping
    folder paths to lists of image filenames.
    """
    image_index = {}
    
    # Image extensions to include
    valid_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
    
    # Walk through all directories
    for root, dirs, files in os.walk(base_path):
        # Get relative path from base
        rel_path = os.path.relpath(root, base_path)
        
        # Convert to forward slashes and prepend 'images/'
        if rel_path == '.':
            folder_key = 'images'
        else:
            folder_key = 'images/' + rel_path.replace('\\', '/')
        
        # Filter image files
        image_files = [
            f for f in files 
            if os.path.splitext(f.lower())[1] in valid_extensions
        ]
        
        # Only add if there are images
        if image_files:
            image_index[folder_key] = sorted(image_files)
            print(f"✓ {folder_key}: {len(image_files)} images")
    
    return image_index

def main():
    print("=" * 60)
    print("Building Image Index")
    print("=" * 60)
    print(f"Scanning: {IMAGE_BASE}")
    print()
    
    # Check if base path exists
    if not os.path.exists(IMAGE_BASE):
        print(f"ERROR: Path not found: {IMAGE_BASE}")
        return
    
    # Build the index
    image_index = build_image_index(IMAGE_BASE)
    
    # Save to JSON
    output_path = os.path.join(os.path.dirname(IMAGE_BASE), OUTPUT_FILE)
    
    # Also save in current directory for easy upload
    local_output = OUTPUT_FILE
    
    with open(local_output, 'w', encoding='utf-8') as f:
        json.dump(image_index, f, indent=2, ensure_ascii=False)
    
    print()
    print("=" * 60)
    print(f"✓ Index saved to: {local_output}")
    print(f"✓ Total folders: {len(image_index)}")
    print(f"✓ Total images: {sum(len(v) for v in image_index.values())}")
    print("=" * 60)
    
    # Print folder summary
    print("\nFolder Summary:")
    print("-" * 40)
    for folder, files in sorted(image_index.items()):
        print(f"  {folder}: {len(files)} files")
    
    # Check for required folders
    print("\nRequired Folders Check:")
    print("-" * 40)
    required = [
        'images/UI',
        'images/Rarity', 
        'images/Trait',
        'images/Trait/thum',
        'images/Terrain',
        'images/WeaponIcon',
        'images/Logo-Series',
        'images/portraits',
        'images/unit_portraits',
        'images/Background'
    ]
    
    for folder in required:
        status = "✓" if folder in image_index else "✗ MISSING"
        count = len(image_index.get(folder, []))
        print(f"  {status} {folder} ({count} files)")

if __name__ == '__main__':
    main()