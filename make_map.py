import os
import json

index = {}
# Scan the images folder
for root, dirs, files in os.walk("images"):
    # Fix slashes for windows
    folder = root.replace("\\", "/")
    # Save only image files
    index[folder] = [f for f in files if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))]

with open("image_index.json", "w") as f:
    json.dump(index, f)

print("Map generated! Check for image_index.json")