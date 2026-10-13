"""Extract the loadable image from a compiled firmware object.

The emulators load a flat image, so something has to turn the compiler's
output into one. Two input shapes are handled:

* a relocatable object (the usual case here) - its .text is the image. The
  firmware is a single function with no global data, so nothing needs
  relocating and no linker is involved at all. This is deliberate: linking a
  bare-metal image needs ld.lld, which is not on PATH everywhere this test
  runs, and the objects are simple enough not to need it.
* a linked executable - every PT_LOAD segment is written at its own virtual
  address.

Either way the result is checked to start at address 0, since that is where
the emulator is told to begin executing.
"""

import struct
import sys
from pathlib import Path

ET_REL, ET_EXEC, ET_DYN = 1, 2, 3
PT_LOAD = 1
SHT_NOBITS = 8


class ImageError(Exception):
    """The object cannot be turned into a flat image."""


def _sections(elf: bytes):
    if len(elf) < 0x40:
        raise ImageError("file is too short to be an ELF header")
    shoff, = struct.unpack_from("<Q", elf, 0x28)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", elf, 0x3A)
    if not shnum:
        return {}
    def sh(i):
        return struct.unpack_from("<IIQQQQIIQQ", elf, shoff + i * shentsize)
    _, _, _, _, strtab_off, strtab_size, _, _, _, _ = sh(shstrndx)
    strtab = elf[strtab_off:strtab_off + strtab_size]
    out = {}
    for i in range(shnum):
        name_off, kind, _, addr, offset, size, _, _, _, _ = sh(i)
        name = strtab[name_off:strtab.index(b"\0", name_off)].decode()
        out[name] = (kind, addr, offset, size)
    return out


def _from_relocatable(elf: bytes) -> bytes:
    sections = _sections(elf)
    if ".text" not in sections:
        raise ImageError("no .text section")
    _, addr, offset, size = sections[".text"]
    if addr:
        raise ImageError(f".text is based at {addr:#x}, not 0")

    relocated = [name for name in sections if name.startswith((".rela.", ".rel."))]
    if relocated:
        # The image would need patching, and this script does not do that.
        raise ImageError(
            "the object needs relocation ("
            + ", ".join(sorted(relocated))
            + "); link it first and pass the executable instead"
        )
    return elf[offset:offset + size]


def _from_executable(elf: bytes) -> bytes:
    e_phoff, = struct.unpack_from("<Q", elf, 0x20)
    e_phentsize, e_phnum = struct.unpack_from("<HH", elf, 0x36)
    segments = []
    for i in range(e_phnum):
        base = e_phoff + i * e_phentsize
        if struct.unpack_from("<I", elf, base)[0] != PT_LOAD:
            continue
        offset, vaddr, _, filesz = struct.unpack_from("<QQQQ", elf, base + 0x08)
        if filesz:
            segments.append((vaddr, elf[offset:offset + filesz]))
    if not segments:
        raise ImageError("no PT_LOAD segments")
    base = min(vaddr for vaddr, _ in segments)
    if base:
        raise ImageError(f"image is linked at {base:#x}, not 0")
    size = max(vaddr + len(data) for vaddr, data in segments)
    image = bytearray(size)
    for vaddr, data in segments:
        image[vaddr:vaddr + len(data)] = data
    return bytes(image)


def to_flat(elf: bytes) -> bytes:
    if elf[:4] != b"\x7fELF":
        raise ImageError("not an ELF file")
    if elf[4] != 2:
        raise ImageError("only 64-bit ELF images are supported")
    if elf[5] != 1:
        raise ImageError("only little-endian images are supported")

    e_type = struct.unpack_from("<H", elf, 0x10)[0]
    if e_type == ET_REL:
        return _from_relocatable(elf)
    if e_type in (ET_EXEC, ET_DYN):
        return _from_executable(elf)
    raise ImageError(f"unsupported ELF type {e_type}")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} <input-object> <output-image>")
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    try:
        image = to_flat(src.read_bytes())
    except ImageError as exc:
        raise SystemExit(f"{src.name}: {exc}") from None
    dst.write_bytes(image)
    print(f"{src.name} -> {dst.name}: {len(image)} bytes")


if __name__ == "__main__":
    main()
