"""Build a tight transparent PNG/ICO from the user-supplied square mascot image."""

from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "2byteasr-icon.jpg"
PNG_OUTPUT = ROOT / "assets" / "2byteasr-icon-transparent.png"
ICO_OUTPUT = ROOT / "assets" / "2byteasr.ico"


def is_edge_white(pixel):
    red, green, blue = pixel
    return min(red, green, blue) >= 228 and max(red, green, blue) - min(red, green, blue) <= 20


def connected_background_mask(image):
    width, height = image.size
    pixels = image.load()
    visited = bytearray(width * height)
    queue = deque()

    def enqueue(x, y):
        offset = y * width + x
        if visited[offset] or not is_edge_white(pixels[x, y]):
            return
        visited[offset] = 1
        queue.append((x, y))

    for x in range(width):
        enqueue(x, 0)
        enqueue(x, height - 1)
    for y in range(height):
        enqueue(0, y)
        enqueue(width - 1, y)

    while queue:
        x, y = queue.popleft()
        if x:
            enqueue(x - 1, y)
        if x + 1 < width:
            enqueue(x + 1, y)
        if y:
            enqueue(x, y - 1)
        if y + 1 < height:
            enqueue(x, y + 1)

    alpha = Image.new("L", image.size, 255)
    alpha_pixels = alpha.load()
    for y in range(height):
        row = y * width
        for x in range(width):
            if visited[row + x]:
                alpha_pixels[x, y] = 0
    # Contract one antialiased background pixel, then soften the cut edge.
    return alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.45))


def main():
    source = Image.open(SOURCE).convert("RGB")
    alpha = connected_background_mask(source)
    rgba = source.convert("RGBA")
    rgba.putalpha(alpha)

    # A modest center crop enlarges the face at taskbar sizes without changing it.
    inset = max(1, round(min(rgba.size) * 0.025))
    rgba = rgba.crop((inset, inset, rgba.width - inset, rgba.height - inset))
    rgba = rgba.resize((512, 512), Image.Resampling.LANCZOS)
    rgba.save(PNG_OUTPUT, format="PNG", optimize=True)
    rgba.save(
        ICO_OUTPUT,
        format="ICO",
        sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(PNG_OUTPUT)
    print(ICO_OUTPUT)


if __name__ == "__main__":
    main()
