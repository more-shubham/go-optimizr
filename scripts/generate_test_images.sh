#!/bin/bash
# Generate test images for go-optimizr testing
# Target: ~1GB of mixed JPEG/PNG images

set -e

OUTPUT_DIR="${1:-./images}"
TARGET_SIZE_MB="${2:-1024}"  # 1GB default

mkdir -p "$OUTPUT_DIR"

echo "Generating test images in $OUTPUT_DIR (target: ${TARGET_SIZE_MB}MB)"
echo "This may take a few minutes..."

current_size=0
count=0

# Image dimensions (varied sizes to simulate real-world)
sizes=("1920x1080" "2560x1440" "3840x2160" "1280x720" "800x600" "4000x3000")
formats=("jpg" "png" "jpg" "jpg" "png" "jpg")  # More JPEGs (common ratio)

while [ $current_size -lt $((TARGET_SIZE_MB * 1024)) ]; do
    # Pick random size and format
    idx=$((RANDOM % ${#sizes[@]}))
    size=${sizes[$idx]}
    format=${formats[$idx]}

    # Create subdirectories to test recursive walk
    subdir=""
    case $((RANDOM % 4)) in
        0) subdir="photos" ;;
        1) subdir="screenshots" ;;
        2) subdir="artwork" ;;
        3) subdir="" ;;  # Root directory
    esac

    if [ -n "$subdir" ]; then
        mkdir -p "$OUTPUT_DIR/$subdir"
        filepath="$OUTPUT_DIR/$subdir/image_${count}.${format}"
    else
        filepath="$OUTPUT_DIR/image_${count}.${format}"
    fi

    # Generate image with random plasma pattern (looks realistic, compresses like real photos)
    if [ "$format" = "jpg" ]; then
        convert -size "$size" plasma:random -quality 85 "$filepath" 2>/dev/null
    else
        convert -size "$size" plasma:random "$filepath" 2>/dev/null
    fi

    # Update size counter (in KB)
    if [ -f "$filepath" ]; then
        file_size=$(stat -f%z "$filepath" 2>/dev/null || stat -c%s "$filepath" 2>/dev/null)
        current_size=$((current_size + file_size / 1024))
        count=$((count + 1))

        # Progress update every 50 images
        if [ $((count % 50)) -eq 0 ]; then
            echo "  Generated $count images ($(( current_size / 1024 ))MB / ${TARGET_SIZE_MB}MB)"
        fi
    fi
done

echo ""
echo "Done! Generated $count images"
echo "Total size: $(du -sh "$OUTPUT_DIR" | cut -f1)"
echo ""
echo "Directory structure:"
find "$OUTPUT_DIR" -type d | head -10
echo ""
echo "Sample files:"
ls -lh "$OUTPUT_DIR" | head -10
