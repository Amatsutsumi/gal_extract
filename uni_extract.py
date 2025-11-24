#!/usr/bin/env python3
import struct
import os
import re
import sys

FIXED_PATH_LEN = 256
HEADER_MAGIC = b"UNIONFILES"
START_OFFSET = 0x10

def read_cstring(bs):
    i = bs.find(b'\x00')
    if i == -1:
        i = len(bs)
    return bs[:i].decode('shift_jis', errors='ignore')

def looks_like_valid_path(name):
    """判断是不是一个正常的路径，而不是 BMP 的前两个字节等垃圾数据"""
    if not name:
        return False
    if len(name) < 3:  # 太短的不可能是路径
        return False
    if any(c in name for c in ['\x00', '\x01', '\x02', '\x03']):
        return False
    # 如果全是不可见字符，也视为无效
    if all(ord(c) < 32 for c in name):
        return False
    # 如果像 "BM8..." 就明显是 BMP 文件头
    if name.startswith("BM"):
        return False
    return True

def sanitize_filename(name):
    """将文件名中非法字符替换为下划线，并限制长度"""
    name = name.replace("\\", os.sep).lstrip(os.sep)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    return name[:200]  # 限制长度，防止路径过长

def extract(input_file, out_dir="output"):
    os.makedirs(out_dir, exist_ok=True)

    with open(input_file, "rb") as f:
        magic = f.read(len(HEADER_MAGIC))
        if magic != HEADER_MAGIC:
            f.seek(0)
            peek = f.read(64)
            if HEADER_MAGIC not in peek:
                raise SystemExit("不是 UNIONFILES（未发现 magic）")
            else:
                f.seek(peek.index(HEADER_MAGIC))

        f.seek(START_OFFSET)

        entries = []
        while True:
            chunk = f.read(FIXED_PATH_LEN)
            if not chunk or len(chunk) < FIXED_PATH_LEN:
                break

            name = read_cstring(chunk)

            if not looks_like_valid_path(name):
                print(f"结束目录解析（遇到无效路径: {name!r}）")
                break

            data = f.read(8)
            if len(data) < 8:
                break
            offset, size = struct.unpack("<II", data)

            uend = f.read(4)
            if uend != b"UEND":
                f.seek(-4, 1)

            entries.append((name, offset, size))

        print(f"发现 {len(entries)} 个条目，开始解包…")

        for name, offset, size in entries:
            if offset == 0 or size == 0:
                print(f"[跳过] 空条目: {name}")
                continue

            safe_name = sanitize_filename(name)
            if not safe_name:
                print(f"[跳过] 非法路径: {name!r}")
                continue

            out_path = os.path.join(out_dir, safe_name)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            f.seek(offset)
            data = f.read(size)
            try:
                with open(out_path, "wb") as out:
                    out.write(data)
                print(f"[OK] {safe_name} ({size} bytes)")
            except OSError as e:
                print(f"[失败] {safe_name}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python extract_unionfiles.py <输入文件> [输出目录]")
        sys.exit(1)

    infile = sys.argv[1]
    outdir = "output" if len(sys.argv) < 3 else sys.argv[2]
    extract(infile, outdir)
