#!/usr/bin/env python3
"""
pacman.py - Magical Pac-Man Contribution Animation Generator
Target: Blessymolcharls/Blessymolcharls

Preserves 100% of the original Platane/snk Snake animation mechanics:
- Authentic GitHub contribution calendar & intensity levels (levels 0-4)
- Exact weekday alignment and grid geometry
- Dynamic animation duration extracted directly from Platane/snk output (never hardcoded)
- True consumption mechanics: active contribution cells vanish instantly into Pac-Man's
  mouth as the jaws contact them, perfectly synchronized across all loops with zero timing drift
- Single Golden Snitch Pac-Man replaces the snake body
- Rotates dynamically to face the movement direction
- Animated chomp jaws & delicate golden wings
- Progress bars at the bottom grow as contributions are consumed
- Generates pacman-dark.svg, pacman.svg, and pacman.gif
"""

import argparse
import io
import math
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def get_snake_svg_source(out_dir, theme="dark"):
    """
    Locates the Snake SVG source:
    1. Checks out_dir/snake-{theme}.svg or out_dir/snake.svg
    2. Checks git remotes/origin/output in the repository directory
    """
    filename = f"snake-{theme}.svg" if theme == "dark" else "snake.svg"
    local_path = os.path.join(out_dir, filename)
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            return f.read()

    # Determine repository root
    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Try git remotes/origin/output or origin/output
    for branch_ref in [f"remotes/origin/output:{filename}", f"origin/output:{filename}", f"output:{filename}"]:
        try:
            res = subprocess.check_output(
                ["git", "show", branch_ref],
                cwd=repo_dir,
                stderr=subprocess.DEVNULL
            ).decode("utf-8")
            if res and "<svg" in res:
                return res
        except Exception:
            pass

    raise RuntimeError(
        f"Could not locate {filename} in {out_dir} or in git output branch. "
        "Ensure Platane/snk step runs before this script or output branch exists."
    )


def transform_snake_to_pacman_svg(snake_svg_content, theme="dark"):
    """
    Transforms Platane/snk SVG into Magical Pac-Man SVG:
    1. Extracts the exact animation duration dynamically (e.g. 26700ms, 27500ms) to ensure
       zero timing drift across endless loops.
    2. Replaces snake rects (s0, s1, s2, s3) with the Golden Snitch Pac-Man character.
    3. Retimes cell disappearance to the exact instant Pac-Man's mouth contacts each cell
       so dots vanish cleanly into Pac-Man's jaws rather than lagging behind.
    4. Modifies movement keyframes to rotate Pac-Man towards the travel direction.
    5. Synchronizes progress bars at the bottom with the mouth-contact timing.
    """
    css_m = re.search(r'<style>(.*?)</style>', snake_svg_content, re.DOTALL)
    if not css_m:
        raise ValueError("Could not find <style> in SVG")
    css = css_m.group(1)

    # Extract dynamic animation duration (e.g. 27500ms, 26700ms)
    dur_m = re.search(r'animation:[^;]*?([0-9]+)ms', css)
    if not dur_m:
        raise ValueError("Could not find animation duration in snake SVG CSS")
    duration_ms = int(dur_m.group(1))

    s0_m = re.search(r'@keyframes s0\{(.*?)\}\.s', css)
    if not s0_m:
        raise ValueError("Could not find @keyframes s0 in SVG")

    entries = re.findall(r'([0-9.,%]+)\{transform:translate\((-?[0-9.]+)px,(-?[0-9.]+)px\)\}', s0_m.group(1))

    # Parse keyframe points: (pct, tx, ty)
    pts = []
    for pct_str, tx_str, ty_str in entries:
        tx = float(tx_str)
        ty = float(ty_str)
        pcts = [float(p.replace('%', '')) for p in pct_str.split(',') if p]
        for p in pcts:
            pts.append((p, tx, ty))

    pts.sort(key=lambda x: x[0])

    def get_pos_at(pct):
        for i in range(len(pts) - 1):
            p1, x1, y1 = pts[i]
            p2, x2, y2 = pts[i+1]
            if p1 <= pct <= p2:
                frac = (pct - p1) / (p2 - p1) if p2 > p1 else 0
                dx = x2 - x1
                dy = y2 - y1
                if dx > 0: ang = 0
                elif dy > 0: ang = 90
                elif dx < 0: ang = 180
                elif dy < 0: ang = 270
                else: ang = 0
                return (x1 + frac * dx, y1 + frac * dy, ang)
        return (pts[-1][1], pts[-1][2], 0)

    # Build rotated keyframes for Pac-Man
    pacman_kf = []
    for i in range(len(pts) - 1):
        p1, x1, y1 = pts[i]
        p2, x2, y2 = pts[i+1]
        dx = x2 - x1
        dy = y2 - y1
        if dx > 0: ang = 0
        elif dy > 0: ang = 90
        elif dx < 0: ang = 180
        elif dy < 0: ang = 270
        else: ang = 0

        pacman_kf.append(f"{p1:.2f}%{{transform:translate({x1:.1f}px,{y1:.1f}px) rotate({ang}deg)}}")
        pacman_kf.append(f"{p2 - 0.01:.2f}%{{transform:translate({x2:.1f}px,{y2:.1f}px) rotate({ang}deg)}}")

    last_p, last_x, last_y = pts[-1]
    pacman_kf.append(f"100%{{transform:translate({last_x:.1f}px,{last_y:.1f}px) rotate(0deg)}}")

    pacman_kf_str = "".join(pacman_kf)

    # Defs for Golden Snitch Pac-Man
    defs_str = """<defs>
<radialGradient id="snitchGold" cx="35%" cy="35%" r="65%">
  <stop offset="0%" stop-color="#FFFDE7"/>
  <stop offset="35%" stop-color="#FFD700"/>
  <stop offset="80%" stop-color="#F59E0B"/>
  <stop offset="100%" stop-color="#B45309"/>
</radialGradient>
<radialGradient id="snitchAura" cx="50%" cy="50%" r="50%">
  <stop offset="0%" stop-color="#FFD700" stop-opacity="0.55"/>
  <stop offset="100%" stop-color="#FFD700" stop-opacity="0"/>
</radialGradient>
<linearGradient id="wingGold" x1="0%" y1="0%" x2="100%" y2="100%">
  <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.95"/>
  <stop offset="60%" stop-color="#FFE082" stop-opacity="0.6"/>
  <stop offset="100%" stop-color="#FFB300" stop-opacity="0.2"/>
</linearGradient>
</defs>"""

    # Pac-Man CSS animations with dynamic duration matching the grid cells exactly
    pacman_css = f"""
/* Golden Snitch Pac-Man character */
@keyframes pacman-motion {{
{pacman_kf_str}
}}
.pacman-runner {{
  transform-origin: 8px 8px;
  animation: pacman-motion {duration_ms}ms linear infinite;
}}
@keyframes chomp-upper {{
  0%, 100% {{ transform: rotate(0deg); }}
  50% {{ transform: rotate(-24deg); }}
}}
@keyframes chomp-lower {{
  0%, 100% {{ transform: rotate(0deg); }}
  50% {{ transform: rotate(24deg); }}
}}
.jaw-upper {{
  animation: chomp-upper 0.28s infinite ease-in-out;
  transform-origin: 8px 8px;
}}
.jaw-lower {{
  animation: chomp-lower 0.28s infinite ease-in-out;
  transform-origin: 8px 8px;
}}
@keyframes wing-flutter {{
  0%, 100% {{ transform: scaleY(1); }}
  50% {{ transform: scaleY(0.65); }}
}}
.wing-top {{
  animation: wing-flutter 0.22s infinite ease-in-out;
  transform-origin: 6px 6px;
}}
.wing-bottom {{
  animation: wing-flutter 0.22s infinite ease-in-out;
  transform-origin: 6px 10px;
}}
@keyframes sparkle {{
  0%, 100% {{ opacity: 0.2; transform: scale(0.7); }}
  50% {{ opacity: 0.95; transform: scale(1.1); }}
}}
.sp1 {{ animation: sparkle 0.9s infinite ease-in-out; transform-origin: 1px 7px; }}
.sp2 {{ animation: sparkle 0.9s infinite ease-in-out 0.45s; transform-origin: -3px 10px; }}
"""

    eye_color = "#161b22" if theme == "dark" else "#ffffff"
    # Single Golden Snitch Pac-Man element
    pacman_elem = f"""<g id="magical-pacman" class="pacman-runner">
  <circle cx="8" cy="8" r="10" fill="url(#snitchAura)"/>
  <path class="wing-top" d="M 6 6 C 1 2 -5 1 -9 4 C -7 7 -1 8 6 7 Z" fill="url(#wingGold)"/>
  <path class="wing-bottom" d="M 6 10 C 1 14 -5 15 -9 12 C -7 9 -1 8 6 9 Z" fill="url(#wingGold)"/>
  <path class="jaw-upper" d="M 8 8 L 15 8 A 7 7 0 0 0 1 8 Z" fill="url(#snitchGold)"/>
  <path class="jaw-lower" d="M 8 8 L 15 8 A 7 7 0 0 1 1 8 Z" fill="url(#snitchGold)"/>
  <circle cx="9" cy="5" r="1" fill="{eye_color}"/>
  <polygon points="0,6.5 1,5 2,6.5 1,8" fill="#FFF9C4" class="sp1"/>
  <polygon points="-4,9.5 -3,8 -2,9.5 -3,11" fill="#FFD700" class="sp2"/>
</g>"""

    # Clean snake styles from CSS
    new_css = re.sub(r'@keyframes s[0-3]\{.*?\}\.s', '', css)
    new_css = re.sub(r'\.s\{.*?\}', '', new_css)
    new_css = re.sub(r'\.s\.s[0-3]\{.*?\}', '', new_css)

    # Standardize dark theme green intensity scale
    if theme == "dark":
        new_css = new_css.replace('--c1:#01311f', '--c1:#0e4429')
        new_css = new_css.replace('--c2:#034525', '--c2:#006d32')
        new_css = new_css.replace('--c3:#0f6d31', '--c3:#26a641')
        new_css = new_css.replace('--c4:#00c647', '--c4:#39d353')

    # Retime cells to mouth contact:
    # Platane/snk sets t2 to when the snake head center (tx+8, ty+8) reaches cell center (cx+6, cy+6).
    # Pac-Man's mouth is at the leading edge (radius 7px ahead in motion direction).
    # Disappearing when the mouth contacts the cell eliminates the visible lag where the cell
    # lingers after being bitten.
    cells = re.findall(r'<rect class="c(?:\s+([^"]+))?"\s+x="([0-9.]+)"\s+y="([0-9.]+)"', snake_svg_content)
    cell_map = {}
    for cls, x, y in cells:
        if cls and 'c' in cls:
            cell_map[cls] = (float(x), float(y))

    cell_kfs = re.findall(r'@keyframes (c[0-9a-z]+)\{([0-9.]+)%\{fill:var\((--c[1-4])\)\}([0-9.]+)%,100%\{fill:var\(--ce\)\}', css)

    for c_name, t1_str, var, t2_str in cell_kfs:
        if c_name not in cell_map:
            continue
        cx, cy = cell_map[c_name]
        cell_cx = cx + 6
        cell_cy = cy + 6
        t2 = float(t2_str)

        mouth_t = t2
        for step in range(int(t2 * 1000), int(max(0, t2 - 1.5) * 1000), -5):
            p = step / 1000.0
            tx, ty, ang = get_pos_at(p)
            rad = math.radians(ang)
            mx = tx + 8 + 7 * math.cos(rad)
            my = ty + 8 + 7 * math.sin(rad)
            if math.hypot(mx - cell_cx, my - cell_cy) <= 6.0:
                mouth_t = p

        new_t1 = max(0.0, mouth_t - 0.02)
        new_t2 = mouth_t

        old_c_pattern = f"@keyframes {c_name}{{{t1_str}%{{fill:var({var})}}{t2_str}%,100%{{fill:var(--ce)}}}}"
        new_c_pattern = f"@keyframes {c_name}{{{new_t1:.2f}%{{fill:var({var})}}{new_t2:.2f}%,100%{{fill:var(--ce)}}}}"
        new_css = new_css.replace(old_c_pattern, new_c_pattern)

        # Retime progress bars (u) so they advance at the exact same moment
        new_css = new_css.replace(f"{t1_str}%{{transform:", f"{new_t1:.2f}%{{transform:")
        new_css = new_css.replace(f"{t2_str}%,", f"{new_t2:.2f}%,")
        new_css = new_css.replace(f",{t1_str}%{{transform:", f",{new_t1:.2f}%{{transform:")

    new_css += pacman_css

    # Replace CSS in SVG
    res = snake_svg_content.replace(css, new_css)
    # Add defs right after style
    res = res.replace('</style>', '</style>' + defs_str)
    # Remove snake body rects
    res = re.sub(r'<rect class="s s[0-3]"[^>]*/>', '', res)
    # Insert Pac-Man character right before </svg>
    res = res.replace('</svg>', pacman_elem + '</svg>')

    return res


def render_pacman_gif(snake_svg_content, out_gif_path):
    """
    Renders the exact animated GIF corresponding to Platane/snk's loop:
    - Dynamic frame count and duration matching snake_svg_content exactly
    - Active cells remain green until chomped by Pac-Man's mouth, then become empty #161b22
    - Pac-Man chomps and rotates along the exact motion vector
    - Progress bars fill dynamically at the bottom
    """
    if not HAS_PIL:
        print("[-] Pillow is not installed. Skipping GIF generation.")
        return

    css_m = re.search(r'<style>(.*?)</style>', snake_svg_content, re.DOTALL)
    css = css_m.group(1)

    dur_m = re.search(r'animation:[^;]*?([0-9]+)ms', css)
    duration_ms = int(dur_m.group(1)) if dur_m else 26700
    total_steps = int(round(duration_ms / 100.0))

    # Path waypoints
    s0_m = re.search(r'@keyframes s0\{(.*?)\}\.s', css)
    entries = re.findall(r'([0-9.,%]+)\{transform:translate\((-?[0-9.]+)px,(-?[0-9.]+)px\)\}', s0_m.group(1))

    key_pts = []
    for pct_str, tx_str, ty_str in entries:
        tx = float(tx_str)
        ty = float(ty_str)
        pcts = [float(p.replace('%', '')) for p in pct_str.split(',') if p]
        for p in pcts:
            key_pts.append((p, tx, ty))
    key_pts.sort(key=lambda p: p[0])

    def get_pos(pct):
        for i in range(len(key_pts) - 1):
            p1, x1, y1 = key_pts[i]
            p2, x2, y2 = key_pts[i+1]
            if p1 <= pct <= p2:
                frac = (pct - p1) / max(1e-5, (p2 - p1))
                dx = x2 - x1
                dy = y2 - y1
                if dx > 0: ang = 0
                elif dy > 0: ang = 90
                elif dx < 0: ang = 180
                elif dy < 0: ang = 270
                else: ang = 0
                return (x1 + frac * dx, y1 + frac * dy, ang)
        return (key_pts[-1][1], key_pts[-1][2], 0)

    # Map cells
    cells = re.findall(r'<rect class="c(?:\s+([^"]+))?"\s+x="([0-9.]+)"\s+y="([0-9.]+)"', snake_svg_content)
    cell_map = {}
    for cls, x, y in cells:
        if cls and 'c' in cls:
            cell_map[cls] = (float(x), float(y))

    # Eaten cells timing matching mouth contact
    eaten_cells = {}
    for m in re.finditer(r'@keyframes (c[0-9a-z]+)\{([0-9.]+)%\{fill:var\((--c[1-4])\)\}([0-9.]+)%,100%\{fill:var\(--ce\)\}', css):
        c_name = m.group(1)
        lvl = int(m.group(3)[-1])
        t2 = float(m.group(4))

        if c_name in cell_map:
            cx, cy = cell_map[c_name]
            cell_cx = cx + 6
            cell_cy = cy + 6
            mouth_t = t2
            for step in range(int(t2 * 1000), int(max(0, t2 - 1.5) * 1000), -5):
                p = step / 1000.0
                tx, ty, ang = get_pos(p)
                rad = math.radians(ang)
                mx = tx + 8 + 7 * math.cos(rad)
                my = ty + 8 + 7 * math.sin(rad)
                if math.hypot(mx - cell_cx, my - cell_cy) <= 6.0:
                    mouth_t = p
            step_idx = int(round((mouth_t / 100.0) * total_steps))
        else:
            step_idx = int(round((t2 / 100.0) * total_steps))

        eaten_cells[c_name] = (step_idx, lvl)

    cell_list = []
    for c_cls, x_str, y_str in cells:
        x = float(x_str)
        y = float(y_str)
        col = int(round((x - 2) / 16))
        row = int(round((y - 2) / 16))
        c_cls = c_cls.strip() if c_cls else ""
        if c_cls in eaten_cells:
            step_idx, lvl = eaten_cells[c_cls]
        else:
            step_idx, lvl = -1, 0
        cell_list.append({
            "col": col,
            "row": row,
            "x": x,
            "y": y,
            "level": lvl,
            "eaten_step": step_idx
        })

    # Precalculate step data for each frame
    step_data = []
    for s in range(total_steps):
        p = (s / float(total_steps)) * 100.0
        step_data.append(get_pos(p))

    level_colors = {
        0: (22, 27, 34),
        1: (14, 68, 41),
        2: (0, 109, 50),
        3: (38, 166, 65),
        4: (57, 211, 83)
    }

    # Dynamically extract progress bar geometry from SVG
    u_rects = re.findall(r'<rect class="u\s+u([0-9]+)"[^>]*height="([0-9.]+)"[^>]*width="([0-9.]+)"[^>]*x="([0-9.]+)"', snake_svg_content)
    u_offsets = []
    for u_idx, u_h, u_w, u_x in u_rects:
        lvl = int(u_idx) + 1
        u_offsets.append((float(u_x), float(u_w), lvl))

    total_by_lvl = {}
    for c in cell_list:
        if c["level"] > 0:
            total_by_lvl[c["level"]] = total_by_lvl.get(c["level"], 0) + 1

    frames = []
    WIDTH, HEIGHT = 880, 206

    for f_idx in range(total_steps):
        img = Image.new("RGB", (WIDTH, HEIGHT), (13, 17, 23))
        draw = ImageDraw.Draw(img)

        # 1. Cells
        for c in cell_list:
            x, y = c["x"], c["y"]
            lvl = c["level"]
            eaten_step = c["eaten_step"]
            if lvl == 0 or (eaten_step != -1 and f_idx >= eaten_step):
                col_rgb = level_colors[0]
            else:
                col_rgb = level_colors[lvl]
            draw.rounded_rectangle([x, y, x + 12, y + 12], radius=2, fill=col_rgb)

        # 2. Progress bars at y=144
        eaten_by_lvl = {1: 0, 2: 0, 3: 0, 4: 0}
        for c in cell_list:
            if c["level"] > 0 and c["eaten_step"] != -1 and f_idx >= c["eaten_step"]:
                eaten_by_lvl[c["level"]] += 1

        for ux, uw, ulvl in u_offsets:
            tot = total_by_lvl.get(ulvl, 1)
            frac = eaten_by_lvl.get(ulvl, 0) / max(1, tot)
            if frac > 0:
                cur_w = uw * frac
                draw.rectangle([ux, 144, ux + cur_w, 144 + 12], fill=level_colors[ulvl])

        # 3. Golden Snitch Pac-Man
        tx, ty, ang = step_data[f_idx]
        cx = tx + 8
        cy = ty + 8
        rad = 7

        chomp = 24 * abs(math.sin(f_idx * 0.45))
        start_deg = ang + chomp
        end_deg = ang + 360 - chomp

        draw.pieslice(
            [cx - rad, cy - rad, cx + rad, cy + rad],
            start=start_deg,
            end=end_deg,
            fill=(255, 215, 0),
            outline=(217, 119, 6)
        )
        wing_y_off = 3 * math.sin(f_idx * 0.9)
        draw.polygon([(cx - 2, cy - 2), (cx - 10, cy - 5 + wing_y_off), (cx - 7, cy - 1)], fill=(255, 235, 150))
        draw.polygon([(cx - 2, cy + 2), (cx - 10, cy + 5 - wing_y_off), (cx - 7, cy + 1)], fill=(255, 235, 150))

        frames.append(img)

    frame_dur = int(round(duration_ms / total_steps))
    frames[0].save(
        out_gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=frame_dur,
        loop=0,
        optimize=False
    )
    print(f"[+] Saved animated GIF to {out_gif_path} ({len(frames)} frames, duration={duration_ms}ms, {os.path.getsize(out_gif_path)} bytes).")


def main():
    parser = argparse.ArgumentParser(description="Magical Pac-Man Contribution Animation Generator")
    parser.add_argument("--user", default="Blessymolcharls", help="GitHub username")
    parser.add_argument("--out", default="dist", help="Output directory")
    parser.add_argument("--format", default="all", choices=["svg", "gif", "all"], help="Output format")
    args = parser.parse_args()

    # Ensure output directory exists and is writable
    if hasattr(os, "geteuid") and os.name != "nt":
        try:
            subprocess.run(["sudo", "chown", "-R", f"{os.geteuid()}:{os.getegid()}", args.out], check=False, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    os.makedirs(args.out, exist_ok=True)

    print(f"[+] Loading Snake animation source for user '{args.user}'...")
    dark_source = get_snake_svg_source(args.out, "dark")
    light_source = get_snake_svg_source(args.out, "light")

    if args.format in ("svg", "all"):
        print("[+] Generating pacman-dark.svg...")
        pacman_dark = transform_snake_to_pacman_svg(dark_source, "dark")
        ET.fromstring(pacman_dark) # validate XML
        dark_out = os.path.join(args.out, "pacman-dark.svg")
        with open(dark_out, "w", encoding="utf-8") as f:
            f.write(pacman_dark)
        print(f"[+] Saved {dark_out} ({len(pacman_dark)} bytes, XML valid).")

        print("[+] Generating pacman.svg...")
        pacman_light = transform_snake_to_pacman_svg(light_source, "light")
        ET.fromstring(pacman_light) # validate XML
        light_out = os.path.join(args.out, "pacman.svg")
        with open(light_out, "w", encoding="utf-8") as f:
            f.write(pacman_light)
        print(f"[+] Saved {light_out} ({len(pacman_light)} bytes, XML valid).")
    if args.format in ("gif", "all"):
        print("[+] Generating pacman.gif...")
        gif_out = os.path.join(args.out, "pacman.gif")
        render_pacman_gif(dark_source, gif_out)

    # Ensure legacy snake assets exist in output directory for backward compatibility
    snake_dark_file = os.path.join(args.out, "snake-dark.svg")
    if not os.path.exists(snake_dark_file):
        with open(snake_dark_file, "w", encoding="utf-8") as f:
            f.write(dark_source)
    snake_light_file = os.path.join(args.out, "snake.svg")
    if not os.path.exists(snake_light_file):
        with open(snake_light_file, "w", encoding="utf-8") as f:
            f.write(light_source)
    snake_gif_file = os.path.join(args.out, "snake.gif")
    if not os.path.exists(snake_gif_file):
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for branch_ref in ["remotes/origin/output:snake.gif", "origin/output:snake.gif", "output:snake.gif"]:
            try:
                gif_bytes = subprocess.check_output(["git", "show", branch_ref], cwd=repo_dir, stderr=subprocess.DEVNULL)
                if gif_bytes:
                    with open(snake_gif_file, "wb") as f:
                        f.write(gif_bytes)
                    break
            except Exception:
                pass

    print("[OK] Magical Pac-Man generation completed successfully!")


if __name__ == "__main__":
    main()
