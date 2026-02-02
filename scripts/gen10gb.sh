#!/bin/bash
# Fast 10GB test image generator

cd /Users/shubham/Developer/go-optimizr/images
TARGET_KB=$((10 * 1024 * 1024))  # 10GB in KB
current_kb=0
count=0

sizes=("1920x1080" "2560x1440" "3840x2160" "1280x720" "4000x3000" "2048x2048")
dirs=("." "photos" "screenshots" "artwork")

echo "Generating 10GB of test images..."
echo "Start: $(date)"

while [ $current_kb -lt $TARGET_KB ]; do
    size=${sizes[$((RANDOM % ${#sizes[@]}))]}
    dir=${dirs[$((RANDOM % ${#dirs[@]}))]}
    
    # Alternate between jpg and png (70% jpg, 30% png)
    if [ $((RANDOM % 10)) -lt 7 ]; then
        ext="jpg"
        convert -size "$size" plasma:fractal -quality 90 "$dir/img_${count}.jpg" 2>/dev/null
    else
        ext="png"
        convert -size "$size" plasma:fractal "$dir/img_${count}.png" 2>/dev/null
    fi
    
    if [ -f "$dir/img_${count}.${ext}" ]; then
        fsize=$(stat -f%z "$dir/img_${count}.${ext}" 2>/dev/null)
        current_kb=$((current_kb + fsize / 1024))
        count=$((count + 1))
        
        if [ $((count % 100)) -eq 0 ]; then
            echo "Progress: $count images, $((current_kb / 1024))MB / 10240MB"
        fi
    fi
done

echo ""
echo "Done: $(date)"
echo "Total: $count images"
du -sh .
