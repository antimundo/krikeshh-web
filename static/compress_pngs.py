#!/usr/bin/env python3
"""
This scripts compresses all .png images on its folder and subfolders

You need to install Pillow to use this script
python3 -m venv .venv
source .venv/bin/activate
pip install Pillow
"""

from pathlib import Path
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

import os
import shutil
import tempfile

MAX_WIDTH = 3840
MAX_SIZE = 1 * 1024 * 1024  # 1 MB
MIN_WIDTH = 320


def human_size(size):
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.2f} MB"
    return f"{size / 1024:.1f} KB"


def save_png(image, path, colors=None):
    """
    Save PNG with optimization.
    If colors is specified, quantize the image to a palette.
    """
    if colors:
        # RGBA needs special handling so transparency is preserved.
        if image.mode == "RGBA":
            image = image.quantize(
                colors=colors,
                method=Image.Quantize.FASTOCTREE,
                dither=Image.Dither.FLOYDSTEINBERG,
            )
        else:
            image = image.convert("RGB").quantize(
                colors=colors,
                method=Image.Quantize.MEDIANCUT,
                dither=Image.Dither.FLOYDSTEINBERG,
            )


    image.save(
        path,
        format="PNG",
        optimize=True,
        compress_level=9,
    )


def compress_image(path):
    original_size = path.stat().st_size

    try:
        with Image.open(path) as img:
            img.load()

            original_width, original_height = img.size

            # Work on a copy so the original remains untouched until success.
            image = img.copy()

        # 1. Resize if width > 3840
        if image.width > MAX_WIDTH:
            new_height = round(image.height * MAX_WIDTH / image.width)

            image = image.resize(
                (MAX_WIDTH, new_height),
                Image.Resampling.LANCZOS,
            )

        # 2. If already <= 1 MB, just save the resized version
        with tempfile.NamedTemporaryFile(
            suffix=".png",
            delete=False,
            dir=path.parent,
        ) as tmp:
            temp_path = Path(tmp.name)

        try:
            save_png(image, temp_path)

            if temp_path.stat().st_size <= MAX_SIZE:
                shutil.move(temp_path, path)

                new_size = path.stat().st_size

                print(
                    f"OK       {path}  "
                    f"{human_size(original_size)} -> {human_size(new_size)}  "
                    f"{original_width}x{original_height} -> "
                    f"{image.width}x{image.height}"
                )
                return

        finally:
            if temp_path.exists():
                temp_path.unlink()

        # 3. Image is still > 1 MB.
        #    Try palette quantization.
        for colors in [256, 128, 64, 32, 16]:
            with tempfile.NamedTemporaryFile(
                suffix=".png",
                delete=False,
                dir=path.parent,
            ) as tmp:
                temp_path = Path(tmp.name)

            try:
                save_png(image, temp_path, colors=colors)

                if temp_path.stat().st_size <= MAX_SIZE:
                    shutil.move(temp_path, path)

                    new_size = path.stat().st_size

                    print(
                        f"COMPRESS {path}  "
                        f"{human_size(original_size)} -> {human_size(new_size)}  "
                        f"{image.width}x{image.height}, "
                        f"{colors} colors"
                    )
                    return

            finally:
                if temp_path.exists():
                    temp_path.unlink()

        # 4. Still too large.
        #    Reduce dimensions progressively until <= 1 MB.
        while image.width > MIN_WIDTH:
            new_width = max(MIN_WIDTH, round(image.width * 0.85))
            new_height = round(image.height * new_width / image.width)

            image = image.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS,
            )

            # Try increasingly aggressive palette compression.
            for colors in [256, 128, 64, 32, 16]:
                with tempfile.NamedTemporaryFile(
                    suffix=".png",
                    delete=False,
                    dir=path.parent,
                ) as tmp:
                    temp_path = Path(tmp.name)

                try:
                    save_png(image, temp_path, colors=colors)

                    if temp_path.stat().st_size <= MAX_SIZE:
                        shutil.move(temp_path, path)

                        new_size = path.stat().st_size

                        print(
                            f"RESIZE   {path}  "
                            f"{human_size(original_size)} -> "
                            f"{human_size(new_size)}  "
                            f"{image.width}x{image.height}, "
                            f"{colors} colors"
                        )
                        return

                finally:
                    if temp_path.exists():
                        temp_path.unlink()

        print(
            f"FAILED   {path}  "
            f"Could not get below 1 MB"
        )

    except Exception as e:
        print(f"ERROR    {path}: {e}")


def main():
    folder = Path.cwd()

    print(f"Scanning: {folder}")
    print(f"Maximum width: {MAX_WIDTH}px")
    print(f"Maximum file size: {human_size(MAX_SIZE)}")
    print()

    pngs = list(folder.rglob("*.png"))
    pngs += list(folder.rglob("*.PNG"))

    # Remove duplicates
    pngs = sorted(set(pngs))

    print(f"Found {len(pngs)} PNG files.\n")

    for path in pngs:
        compress_image(path)


if __name__ == "__main__":
    main()

