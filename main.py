#!/usr/bin/env python3
"""Procedural mango — one ingredient, big and delicious."""
import math, struct, zlib, os

W, H = 512, 512
OUT = "/output/entry.png"

def clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))

def lerp(a, b, t):
    return a + (b - a) * t

def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)

def noise_simple(x, y):
    n = int(math.sin(x * 127.1 + y * 311.7) * 43758.5453)
    n = (n >> 16) & 0xff
    return n / 255.0

def fbm(x, y, octaves=6, seed=0):
    val = 0.0
    amp = 1.0
    freq = 1.0
    for _ in range(octaves):
        val += amp * (noise_simple(x * freq + seed, y * freq + seed) - 0.5)
        amp *= 0.5
        freq *= 2.0
    return val * 2.0

def soft_ellipse(x, y, cx, cy, rx, ry, sharp=1.0):
    dx, dy = (x - cx) / rx, (y - cy) / ry
    d = math.sqrt(dx*dx + dy*dy)
    if d > 1.0:
        return 0.0
    return smoothstep(max(0.0, (1.0 - d) * sharp))

def vdist(x1, y1, x2, y2):
    return math.sqrt((x1-x2)**2 + (y1-y2)**2)

# Scene parameters
MANGO_CX, MANGO_CY = 256, 260
MANGO_RX, MANGO_RY = 180, 150
MANGO_ROT = math.radians(-15)
PLATE_CX, PLATE_CY = 256, 300
PLATE_RX, PLATE_RY = 220, 220

def pixel(x, y):
    # Table surface
    tdx, tdy = x - 256, y - 400
    tdist = math.sqrt(tdx*tdx + tdy*tdy)
    table_warm = 0.0
    if tdist < 400:
        table_warm = smoothstep(max(0.0, (400 - tdist) / 100)) * 0.3

    # Plate
    plate_mask = soft_ellipse(x, y, PLATE_CX, PLATE_CY, PLATE_RX, PLATE_RY, sharp=3.0)
    plate_light = 240 - table_warm * 20
    plate_r = clamp(plate_light + 10)
    plate_g = clamp(plate_light + 5)
    plate_b = clamp(plate_light - 15)

    # Mango rotated coords
    mx, my = x - MANGO_CX, y - MANGO_CY
    cos_r, sin_r = math.cos(-MANGO_ROT), math.sin(-MANGO_ROT)
    rx = mx * cos_r - my * sin_r
    ry = mx * sin_r + my * cos_r
    mango_mask = soft_ellipse(x, y, MANGO_CX, MANGO_CY, MANGO_RX, MANGO_RY, sharp=2.0)

    # Nose bulge
    nose_x = MANGO_CX + 120 * cos_r
    nose_y = MANGO_CY + 120 * sin_r
    nose_mask = soft_ellipse(x, y, nose_x, nose_y, 40, 50, sharp=1.5) * 0.7

    # Gradient from stem to tip
    pos_x = rx / MANGO_RX
    tip_ratio = (pos_x + 1.0) / 2.0

    stem_r, stem_g, stem_b = 220, 200, 30
    mid_r, mid_g, mid_b = 240, 140, 20
    tip_r, tip_g, tip_b = 200, 40, 10

    color_t = smoothstep(tip_ratio)
    base_r = lerp(stem_r, mid_r, min(1.0, color_t * 2.0))
    base_g = lerp(stem_g, mid_g, min(1.0, color_t * 2.0))
    base_b = lerp(stem_b, mid_b, min(1.0, color_t * 2.0))
    if color_t > 0.5:
        ct2 = (color_t - 0.5) * 2.0
        base_r = lerp(base_r, tip_r, smoothstep(ct2))
        base_g = lerp(base_g, tip_g, smoothstep(ct2))
        base_b = lerp(base_b, tip_b, smoothstep(ct2))

    # Surface noise
    nv = fbm(x * 0.01, y * 0.01, 4, seed=42) * 15
    base_r += nv
    base_g += nv * 0.7
    base_b += nv * 0.3

    # Red blush
    blush_angle = math.atan2(ry, rx)
    blush = math.cos(blush_angle) * 0.5 + 0.5
    blush_strength = smoothstep(max(0.0, (blush - 0.5)) * 3.0)
    base_r = lerp(base_r, 200, blush_strength * 0.4)
    base_g = lerp(base_g, 20, blush_strength * 0.4)
    base_b = lerp(base_b, 10, blush_strength * 0.3)

    # Lighting
    light_dx, light_dy = -80, -120
    light_dist = math.sqrt(light_dx**2 + light_dy**2)

    spec_x, spec_y = MANGO_CX - 60, MANGO_CY - 80
    spec_dist = vdist(x, y, spec_x, spec_y)
    spec_strength = math.exp(-spec_dist**2 / (2 * 30**2))

    spec2_x, spec2_y = MANGO_CX - 30, MANGO_CY - 50
    spec2_dist = vdist(x, y, spec2_x, spec2_y)
    spec2_strength = math.exp(-spec2_dist**2 / (2 * 20**2)) * 0.5

    shadow_x, shadow_y = MANGO_CX + 80, MANGO_CY + 20
    shadow_dist = vdist(x, y, shadow_x, shadow_y)
    shadow_strength = 1.0 - math.exp(-shadow_dist**2 / (2 * 80**2))
    shadow_strength = max(0.0, min(1.0, shadow_strength))

    rim_strength = mango_mask * (1 - smoothstep(mango_mask)) * 2.0
    rim_strength = min(1.0, rim_strength * 0.5)

    r, g, b = base_r, base_g, base_b

    # Diffuse
    dot = (light_dx * (x - MANGO_CX) + light_dy * (y - MANGO_CY)) / (light_dist * MANGO_RX)
    diffuse = 0.6 + 0.4 * smoothstep(max(0.0, dot))
    r *= diffuse
    g *= diffuse
    b *= diffuse

    # Specular
    r += spec_strength * 180 + spec2_strength * 120
    g += spec_strength * 150 + spec2_strength * 100
    b += spec_strength * 80 + spec2_strength * 60

    # Shadow
    r *= (1 - shadow_strength * 0.35)
    g *= (1 - shadow_strength * 0.35)
    b *= (1 - shadow_strength * 0.35)

    # Rim light
    r += rim_strength * 80
    g += rim_strength * 50
    b += rim_strength * 20

    # Detail noise
    dn = fbm(x * 0.03, y * 0.03, 5, seed=99) * 8
    r += dn
    g += dn * 0.8
    b += dn * 0.5

    total_mask = min(1.0, mango_mask + nose_mask)
    r *= total_mask
    g *= total_mask
    b *= total_mask

    # Stem
    stem_mask = 0.0
    for sx, sy in [(MANGO_CX - 15, MANGO_CY - 145), (MANGO_CX + 5, MANGO_CY - 155)]:
        sd = vdist(x, y, sx, sy)
        stem_mask = max(stem_mask, max(0.0, 1.0 - sd / 15))
    stem_mask *= smoothstep(max(0.0, 1.0 - abs((x - MANGO_CX + 5) / 20.0)))
    if stem_mask > 0:
        r = lerp(r, 80, stem_mask * 0.9)
        g = lerp(g, 60, stem_mask * 0.9)
        b = lerp(b, 20, stem_mask * 0.9)

    # Leaf
    leaf_mask = 0.0
    for i in range(8):
        ld = vdist(x, y, MANGO_CX + 20 + i * 8, MANGO_CY - 140 + i * 3)
        leaf_mask = max(leaf_mask, max(0.0, 1.0 - ld / 18))
    leaf_mask *= smoothstep(max(0.0, 1.0 - abs((y - MANGO_CY + 90) / 40.0)))
    if leaf_mask > 0:
        r = lerp(r, 60, leaf_mask * 0.9)
        g = lerp(g, 140, leaf_mask * 0.9)
        b = lerp(b, 30, leaf_mask * 0.9)

    # Plate shadow
    if plate_mask > 0 and mango_mask < 0.1:
        sp_dist = vdist(x, y, MANGO_CX + 40, MANGO_CY + 60)
        sh = math.exp(-sp_dist**2 / (2 * 50**2)) * 0.25
        if sh > 0.001:
            r = lerp(r, plate_r, sh)
            g = lerp(g, plate_g, sh)
            b = lerp(b, plate_b, sh)

    # Plate detail
    if plate_mask > 0 and mango_mask < 0.01:
        pn = fbm(x * 0.005, y * 0.005, 2, seed=77) * 5
        r = lerp(r, plate_r + pn, plate_mask * 0.95)
        g = lerp(g, plate_g + pn * 0.9, plate_mask * 0.95)
        b = lerp(b, plate_b + pn * 0.5, plate_mask * 0.95)

    # Table
    if plate_mask < 0.01:
        tn = fbm(x * 0.008, y * 0.008, 3, seed=55) * 15
        tr = 160 + tn
        tg = 120 + tn * 0.7
        tb = 80 + tn * 0.3
        edge_dist = vdist(x, y, 256, 256)
        ef = smoothstep(max(0.0, (edge_dist - 200)) / 100)
        tr = lerp(tr, 100, ef)
        tg = lerp(tg, 70, ef)
        tb = lerp(tb, 50, ef)
        r, g, b = tr, tg, tb

    # Vignette
    vd = vdist(x, y, 256, 256)
    vg = 1.0 - smoothstep(max(0.0, (vd - 180)) / 120) * 0.3
    r *= vg
    g *= vg
    b *= vg

    return (clamp(r), clamp(g), clamp(b))

def build_png():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pixels = []
    for y in range(H):
        row = []
        for x in range(W):
            r, g, b = pixel(x, y)
            row.extend([r, g, b])
        pixels.append(bytes([0] + row))
    raw = b''.join(pixels)
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = make_chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0))
    idat = make_chunk(b'IDAT', zlib.compress(raw))
    iend = make_chunk(b'IEND', b'')
    with open(OUT, 'wb') as f:
        f.write(sig + ihdr + idat + iend)

def make_chunk(chunk_type, data):
    chunk = struct.pack('>I', len(data)) + chunk_type + data
    crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff)
    return chunk + crc

if __name__ == '__main__':
    build_png()
    sz = os.path.getsize(OUT)
    print(f"Written: {OUT}  ({sz} bytes)")
