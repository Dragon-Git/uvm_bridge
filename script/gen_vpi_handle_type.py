import re

def extract_constants(file_path):
    with open(file_path, 'r') as file:
        content = file.read()

    # 使用正则表达式匹配 #define 常数定义
    pattern = re.compile(r'#define\s+(vpi\w+|cb\w+)\s+(\d+)')
    matches = pattern.findall(content)

    # 生成输出
    for match in matches:
        constant_name = match[0]
        print(f'vpi.attr("{constant_name}") = {constant_name};')

# 指定输入文件路径
file_path = 'inc/vpi_user.h'
extract_constants(file_path)
file_path = 'inc/sv_vpi_user.h'
extract_constants(file_path)
