import argparse
import cv2
import numpy as np
import matplotlib.pyplot as plt
import colour

# ---------------------- Functions ----------------------

def luminance(rgb):
    """Compute luminance (0–1) from RGB values (0–255)."""
    r, g, b = rgb / 255.0
    return 0.299 * r + 0.587 * g + 0.114 * b

def rgb_to_hsl(rgb):
    """Convert RGB (0–255) to HSL values (0–1) using colour-science."""
    arr = np.array(rgb, dtype=float) / 255.0
    hsl = colour.RGB_to_HSL(arr)
    return float(hsl[0]), float(hsl[1]), float(hsl[2])

def create_mask(img, low_thresh=0.3, high_thresh=0.7, channel="luminance",
                invert=False, random_offset=0.0):
    """
    Create binary mask based on luminance or HSL thresholds.
    channel: "luminance", "hsl_h", "hsl_s", "hsl_l"
    thresholds: values between 0–1
    """
    h, w, _ = img.shape
    mask = np.zeros((h, w), dtype=np.uint8)

    for y in range(h):
        for x in range(w):
            pixel = img[y, x]
            if channel == "luminance":
                val = luminance(pixel)
            else:
                hsl = rgb_to_hsl(pixel)
                if channel == "hsl_h": val = hsl[0]
                elif channel == "hsl_s": val = hsl[1]
                elif channel == "hsl_l": val = hsl[2]

            if random_offset > 0:
                val = np.clip(val + np.random.uniform(-random_offset, random_offset), 0, 1)

            if low_thresh <= val <= high_thresh:
                mask[y, x] = 1

    if invert:
        mask = 1 - mask
    return mask

def identify_spans(mask, horizontal=True):
    """
    Identify contiguous spans where mask=1.
    Returns [(row/col, start, end), ...]
    """
    spans = []
    h, w = mask.shape

    if horizontal:
        for y in range(h):
            x = 0
            while x < w:
                if mask[y, x]:
                    start = x
                    while x < w and mask[y, x]:
                        x += 1
                    spans.append((y, start, x))
                x += 1
    else:
        for x in range(w):
            y = 0
            while y < h:
                if mask[y, x]:
                    start = y
                    while y < h and mask[y, x]:
                        y += 1
                    spans.append((x, start, y))
                y += 1
    return spans

def sort_span(span_pixels, metric="luminance", reverse=False):
    """
    Sort pixels in a span by chosen metric.
    """
    if metric == "luminance":
        keys = [float(luminance(p)) for p in span_pixels]
    elif metric == "r":
        keys = [float(p[0]) for p in span_pixels]
    elif metric == "g":
        keys = [float(p[1]) for p in span_pixels]
    elif metric == "b":
        keys = [float(p[2]) for p in span_pixels]
    elif metric in ("hsl_h", "hsl_s", "hsl_l"):
        keys = []
        for p in span_pixels:
            h, s, l = rgb_to_hsl(p)
            if metric == "hsl_h": keys.append(float(h))
            elif metric == "hsl_s": keys.append(float(s))
            else: keys.append(float(l))
    else:
        keys = list(range(len(span_pixels)))  # fallback

    sorted_indices = sorted(range(len(span_pixels)),
                            key=lambda i: keys[i],
                            reverse=reverse)
    sorted_pixels = [span_pixels[i] for i in sorted_indices]
    return np.array(sorted_pixels, dtype=np.uint8)

def pixel_sort(img, low_thresh=0.3, high_thresh=0.7,
               channel="luminance", invert=False, random_offset=0.0,
               horizontal=True, metric="luminance", reverse=False, gamma=1.0):
    """Complete pixel sorting pipeline."""
    out = img.copy()
    mask = create_mask(img, low_thresh, high_thresh, channel, invert, random_offset)
    spans = identify_spans(mask, horizontal)

    for span in spans:
        if horizontal:
            y, start, end = span
            span_pixels = [out[y, x] for x in range(start, end)]
            sorted_span = sort_span(span_pixels, metric, reverse)
            out[y, start:end] = sorted_span
        else:
            x, start, end = span
            span_pixels = [out[y, x] for y in range(start, end)]
            sorted_span = sort_span(span_pixels, metric, reverse)
            for j, y in enumerate(range(start, end)):
                out[y, x] = sorted_span[j]

    # gamma correction
    if gamma != 1.0:
        out = np.clip(((out/255.0) ** (1/gamma)) * 255, 0, 255).astype(np.uint8)
    return out

# ---------------------- Main ----------------------

def main():
    print("Pixel Sorting Art Generator")
    print("---------------------------")
    
    parser = argparse.ArgumentParser(description="Pixel sorting art generator")
    parser.add_argument("input", help="Input image path")
    parser.add_argument("output", help="Output image path")
    parser.add_argument("--low", type=float, default=0.2, help="Low threshold (default=0.2)")
    parser.add_argument("--high", type=float, default=0.8, help="High threshold (default=0.8)")
    parser.add_argument("--channel", choices=["luminance", "hsl_h", "hsl_s", "hsl_l"],
                        default="luminance", help="Channel to threshold (default=luminance)")
    parser.add_argument("--invert", action="store_true", help="Invert mask")
    parser.add_argument("--random_offset", type=float, default=0.0, help="Random offset (default=0.0)")
    parser.add_argument("--vertical", action="store_true", help="Sort vertically instead of horizontally")
    parser.add_argument("--metric", choices=["luminance","r","g","b","hsl_h","hsl_s","hsl_l"],
                        default="hsl_l", help="Metric to sort by (default=hsl_l)")
    parser.add_argument("--reverse", action="store_true", help="Reverse sorting order")
    parser.add_argument("--gamma", type=float, default=1.2, help="Gamma correction (default=1.2)")
    parser.add_argument("--show", action="store_true", help="Show plots before saving")

    args = parser.parse_args()

    img = cv2.imread(args.input)
    if img is None:
        raise FileNotFoundError(f"Could not open {args.input}")
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    sorted_img = pixel_sort(img,
                            low_thresh=args.low,
                            high_thresh=args.high,
                            channel=args.channel,
                            invert=args.invert,
                            random_offset=args.random_offset,
                            horizontal=not args.vertical,
                            metric=args.metric,
                            reverse=args.reverse,
                            gamma=args.gamma)

    if args.show:
        plt.figure(figsize=(12, 6))
        plt.subplot(121); plt.imshow(img); plt.title("Original")
        plt.subplot(122); plt.imshow(sorted_img); plt.title("Pixel Sorted")
        plt.show()

    # Save result
    cv2.imwrite(args.output, cv2.cvtColor(sorted_img, cv2.COLOR_RGB2BGR))
    print(f"Saved output to {args.output}")

if __name__ == "__main__":
    main()


'''
python pixel_sort.py images/NightMarket.jpg output/NightMarket.jpg --show
'''