#!/usr/bin/env python3
"""生成VPI属性头文件"""
import re
import sys
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: generate_vpi_attr.py <source_dir>")
        sys.exit(1)
    
    source_dir = Path(sys.argv[1])
    
    # 读取VPI头文件内容
    vpi_user_h = source_dir / "inc" / "vpi_user.h"
    sv_vpi_user_h = source_dir / "inc" / "sv_vpi_user.h"
    
    content = vpi_user_h.read_text() + sv_vpi_user_h.read_text()
    
    # 提取VPI和cb宏定义
    matches = re.findall(r'#define\s+(vpi\w+|cb\w+)\s+(\d+)', content)
    
    # 生成属性赋值语句
    vpi_attr = [f'vpi.attr("{m[0]}") = {m[0]};' for m in matches]
    
    # 写入输出文件
    output_file = source_dir / "inc" / "vpi_attr.h"
    output_file.write_text('\n'.join(vpi_attr))
    
    print(f"Generated {output_file} with {len(vpi_attr)} attributes")

if __name__ == "__main__":
    main()
