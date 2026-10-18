"""Regenerate the high-res node header and toolbar icons from their 40 px Maya originals.

Reads tools/icon_src (<type>.png, toolbar/<name>.png: Maya's _200 icons, kept as a stable input),
upscales each 4x with realesrgan-ncnn-vulkan, downsamples to --size with an alpha-aware Lanczos,
and writes RGBA over the matching file in nodex/icons. Re-running always starts from the 40 px
sources, never from an already upscaled file.

The upscaler is a dev-time tool, not shipped: the portable build from
https://github.com/xinntao/Real-ESRGAN/releases (realesrgan-ncnn-vulkan-*-windows.zip).
Runs with system Python + Pillow (mayapy has no Pillow).
toolbar/openBar.png (the 14x40 group grip) has no source: it is not square and stays Maya's own.

Usage:
  python tools/upscale_icons.py --upscaler path/to/realesrgan-ncnn-vulkan.exe [--model realesrgan-x4plus-anime] [--size 128]
  python tools/upscale_icons.py --check [--size 128]    # changes nothing, exit 1 if a target is missing or not size x size
  --only "toolbar/*" limits either mode to the sources matching that pattern.
"""
import argparse
import fnmatch
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops, ImageFilter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root
SRC = os.path.join(HERE, "tools", "icon_src")
DST = os.path.join(HERE, "nodex", "icons")


def sources(only="*"):
    """Relative paths (forward slashes) of every source PNG; the layout mirrors nodex/icons."""
    out = []
    for base, _, files in os.walk(SRC):
        for f in sorted(files):
            if f.endswith(".png"):
                out.append(os.path.relpath(os.path.join(base, f), SRC).replace("\\", "/"))
    return sorted(r for r in out if fnmatch.fnmatch(r, only))


def bleed(im):
    """Fill the RGB under fully transparent pixels with the nearby opaque colour.

    Maya's icons carry white or grey under alpha 0; the upscaler is not alpha-aware and would
    drag that into the edge (a halo). Growing rings of alpha-weighted box blurs (the RGBa round
    trip premultiplies and divides) push the edge colour outwards; the alpha is put back after."""
    alpha = im.getchannel("A")
    out = im.copy()
    known = alpha.point(lambda v: 255 if v else 0)
    for r in (1, 2, 4, 8, 16, 32):
        if known.getextrema()[0] == 255:
            break
        probe = out.copy()
        probe.putalpha(known)
        blur = probe.convert("RGBa").filter(ImageFilter.BoxBlur(r)).convert("RGBA")
        reach = blur.getchannel("A").point(lambda v: 255 if v else 0)
        out.paste(blur, mask=ImageChops.subtract(reach, known))
        known = ImageChops.lighter(known, reach)
    out.putalpha(alpha)
    return out


def upscale(exe, model, src, tmp, name):
    """4x upscale of one RGBA image through the ncnn exe; returns the 4x RGBA image."""
    inp, outp = os.path.join(tmp, "in.png"), os.path.join(tmp, "out.png")
    bleed(src).save(inp)
    p = subprocess.run([exe, "-i", inp, "-o", outp, "-n", model, "-s", "4", "-f", "png"],
                       capture_output=True, text=True)
    if p.returncode or not os.path.isfile(outp):
        sys.exit("upscaler failed on %s:\n%s%s" % (name, p.stdout, p.stderr))
    big = Image.open(outp).convert("RGBA")
    big.load()
    os.remove(outp)
    if big.size != (src.width * 4, src.height * 4):
        sys.exit("upscaler returned %dx%d for %s" % (big.width, big.height, name))
    return big


def downscale(big, size):
    """Lanczos in premultiplied space, so transparent RGB never bleeds into the edge."""
    return big.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")


def check(size, only):
    bad = 0
    for rel in sources(only):
        path = os.path.join(DST, rel)
        if not os.path.isfile(path):
            print("MISS %-30s missing" % rel)
            bad += 1
            continue
        im = Image.open(path)
        if im.size != (size, size) or im.mode != "RGBA":
            print("MISS %-30s %dx%d %s" % (rel, im.width, im.height, im.mode))
            bad += 1
        else:
            print("OK   %-30s %dx%d" % (rel, im.width, im.height))
    return bad


def build(exe, model, size, only):
    with tempfile.TemporaryDirectory() as tmp:
        for rel in sources(only):
            src = Image.open(os.path.join(SRC, rel)).convert("RGBA")
            out = downscale(upscale(exe, model, src, tmp, rel), size)
            dst = os.path.join(DST, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            out.save(dst, optimize=True)
            print("OK   %-30s %dx%d -> %dx%d" % (rel, src.width, src.height, size, size))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--upscaler", help="path to realesrgan-ncnn-vulkan(.exe)")
    ap.add_argument("--model", default="realesrgan-x4plus-anime")
    ap.add_argument("--size", type=int, default=128)
    ap.add_argument("--check", action="store_true", help="only verify the shipped icons, change nothing")
    ap.add_argument("--only", default="*", help='glob on the source path, e.g. "toolbar/*"')
    a = ap.parse_args()
    if a.check:
        sys.exit(1 if check(a.size, a.only) else 0)
    if not a.upscaler:
        ap.error("--upscaler is required unless --check is given")
    if not os.path.isfile(a.upscaler):
        ap.error("no upscaler at %s" % a.upscaler)
    build(a.upscaler, a.model, a.size, a.only)


if __name__ == "__main__":
    main()
