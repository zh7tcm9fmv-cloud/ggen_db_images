import os
from PIL import Image

def convert_images_to_webp(folder_path):
    """Convert all image files to WebP format recursively, skipping already converted ones."""
    
    # Supported image extensions
    supported_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.gif', '.ico'}
    
    # Verify the folder exists
    if not os.path.exists(folder_path):
        print(f"Error: Folder '{folder_path}' does not exist.")
        return
    
    # Get all supported image files recursively
    image_files = []
    for root, dirs, files in os.walk(folder_path):
        for f in files:
            if os.path.splitext(f)[1].lower() in supported_extensions:
                # Skip existing webp files
                if os.path.splitext(f)[1].lower() == '.webp':
                    continue
                image_files.append((root, f))
    
    if not image_files:
        print("No image files found in the folder(s).")
        return
    
    converted_count = 0
    skipped_count = 0
    error_count = 0
    
    print(f"Found {len(image_files)} image file(s) across all folders.\n")
    
    for root, image_file in image_files:
        image_path = os.path.join(root, image_file)
        webp_filename = os.path.splitext(image_file)[0] + '.webp'
        webp_path = os.path.join(root, webp_filename)
        
        # Show folder path for reference
        relative_folder = os.path.relpath(root, folder_path)
        display_folder = relative_folder if relative_folder != '.' else '(root folder)'
        
        # Skip if WebP version already exists
        if os.path.exists(webp_path):
            print(f"[{display_folder}] ⏭ Skipped: {image_file}")
            skipped_count += 1
            continue
        
        # Convert image to WebP
        try:
            with Image.open(image_path) as img:
                # Handle transparency and different color modes
                if img.mode in ('RGBA', 'LA'):
                    img.save(webp_path, 'WEBP', quality=80)
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                    img.save(webp_path, 'WEBP', quality=80)
                else:
                    img.save(webp_path, 'WEBP', quality=80)
            
            print(f"[{display_folder}] ✅ Converted: {image_file}")
            converted_count += 1
        except Exception as e:
            print(f"[{display_folder}] ❌ Error converting {image_file}: {e}")
            error_count += 1
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Summary:")
    print(f"  Converted: {converted_count}")
    print(f"  Skipped:   {skipped_count}")
    print(f"  Errors:    {error_count}")
    print(f"  Total:     {len(image_files)}")
    print(f"{'='*50}")


if __name__ == "__main__":
    folder_path = r"C:\Users\Mikew0911\Desktop\ggen_db_images\images"
    convert_images_to_webp(folder_path)