from json import dumps
from math import ceil
from os.path import join, normpath, split, splitext

from Crypto.Cipher import AES
from PIL import Image
from progressbar import AdaptiveETA, Bar, Percentage, ProgressBar, SimpleProgress, Timer

from modules.AES import encrypt
from modules.encrypt_image import generate_encrypted_image, get_encrypted_lists
from modules.loader import get_instances

program = get_instances()

if 'path' not in program.parameter:
    program.logger.error('没有输入文件')
    exit()
program.parameter['path'] = normpath(program.parameter['path'])
img = Image.open(program.parameter['path'])
size = img.size
program.logger.info(f'导入大小：{size[0]}x{size[1]}')

rgb_mapping = program.parameter['mapping']
col = program.parameter['col']
row = program.parameter['row']
pw = program.parameter['password']
has_pw = True if pw != 100 else False
name, suffix = splitext(program.parameter['path'])
suffix = program.parameter['format'] if 'format' in program.parameter else 'png'
suffix.strip('.')
if rgb_mapping and suffix.upper() in ['JPG', 'JPEG', 'WMF', 'WEBP']:
    rgb_mapping = False
    program.logger.warning('你指定了一个有损压缩的图像格式来保存文件，已自动关闭通道映射')

block_width = ceil(size[0] / col)
block_height = ceil(size[1] / row)
program.logger.info(f'分块数量：{col}x{row}; 分块大小：{block_width}x{block_height}')
widgets = [Percentage(), ' ', SimpleProgress(), ' ', Bar('█'), ' ', Timer(), ' ', AdaptiveETA()]
program.logger.info('开始处理')
program.logger.info('正在分割原图')

bar = ProgressBar(max_value=col * row, widgets=widgets)
regions, flip_list = get_encrypted_lists(img, pw, row, col, block_width, block_height, bar=bar)

program.logger.info(f'分割完成，补全后大小：{block_width * col}x{block_height * row}')

program.logger.info('正在重组')
bar = ProgressBar(max_value=col * row, widgets=widgets)
new_image = generate_encrypted_image(regions, flip_list, rgb_mapping, row, col, block_width, block_height, bar=bar)

program.logger.info('重组完成，正在保存文件')
name = f"{name.replace('-decrypted', '')}-encrypted.{suffix}"
path, file = split(program.parameter['path'])
new_image.save(name, format='jpeg' if suffix == 'jpg' else suffix, quality=100)
json = {
    'width': size[0],
    'height': size[1],
    'col': col,
    'row': row,
    'has_password': has_pw,
    'password_base64': encrypt(AES.MODE_CFB, pw, 'PASS', str(size[0]) + str(size[1]), True) if has_pw else 0,
    'rgb_mapping': rgb_mapping
}
with open(join(path, name), "a") as f:
    f.write('\n' + dumps(json, separators=(',', ':')))
