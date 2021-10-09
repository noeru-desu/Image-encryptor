'''
Author       : noeru_desu
Date         : 2021-09-30 20:33:30
LastEditors  : noeru_desu
LastEditTime : 2021-10-09 21:02:21
Description  : 批量加密功能
'''
from json import dumps
from math import ceil
from os import makedirs
from os.path import exists, join, split, splitext

from Crypto.Cipher import AES
from PIL import Image, UnidentifiedImageError
from PIL.Image import EXTENSION, DecompressionBombWarning
from PIL.Image import init as PIL_init
from progressbar import Bar, Percentage, ProgressBar, SimpleProgress

from image_encryptor.utils.AES import encrypt
from image_encryptor.modules.image_cryptor import XOR_image, generate_encrypted_image, map_image
from image_encryptor.modules.loader import load_program
from image_encryptor.utils.utils import calculate_formula_string, fake_bar, pause, walk_file


def encrypt_image(path, parameters, save_relative_path):
    try:
        image = Image.open(path).convert('RGBA')
    except FileNotFoundError:
        return split(path)[1], '文件不存在'
    except UnidentifiedImageError:
        return split(path)[1], '无法打开或识别图像格式，或输入了不受支持的格式'
    except DecompressionBombWarning:
        return split(path)[1], '图片像素量过多，为防止被解压炸弹DOS攻击，自动跳过'
    except Exception as e:
        return split(path)[1], repr(e)

    size = image.size

    if isinstance(parameters['row'], str):
        parameters['row'], error = calculate_formula_string(parameters['row'], width=size[0], height=size[1])
        if error is not None:
            return split(path)[1], f'动态运算切割行数参数时出现错误：{error}'
        elif parameters['row'] < 1:
            return split(path)[1], f"动态运算的切割行数参数不正确：切割行数小于1 (结果为{parameters['row']})"
        elif parameters['row'] > size[1]:
            return split(path)[1], f"动态运算的切割行数参数不正确：切割行数大于图片宽度 (结果为{parameters['row']})"

    if isinstance(parameters['col'], str):
        parameters['col'], error = calculate_formula_string(parameters['col'], width=size[0], height=size[1])
        if error is not None:
            return split(path)[1], f'动态运算切割列数参数时出现错误：{error}'
        elif parameters['col'] < 1:
            return split(path)[1], f"动态运算的切割列数参数不正确：切割列数小于1 (结果为{parameters['col']})"
        elif parameters['col'] > size[0]:
            return split(path)[1], f"动态运算的切割列数参数不正确：切割列数大于图片宽度 (结果为{parameters['col']})"

    has_password = True if parameters['password'] != 100 else False
    name, suffix = splitext(split(path)[1])
    suffix = parameters['format'] if parameters['format'] is not None else 'png'
    suffix = suffix.strip('.')

    block_width = ceil(size[0] / parameters['col'])
    block_height = ceil(size[1] / parameters['row'])

    if parameters['normal_encryption']:
        bar = fake_bar()
        regions, pos_list, flip_list = map_image(image, parameters['password'], False, parameters['row'], parameters['col'], block_width, block_height, bar)

        new_image = generate_encrypted_image(regions, pos_list, flip_list, (block_width * parameters['col'], block_height * parameters['row']), parameters['mapping'], bar)
    else:
        new_image = image

    if parameters['xor_rgb']:
        new_image = XOR_image(new_image, parameters['password'], parameters['xor_alpha'])

    name = f"{name.replace('-decrypted', '')}-encrypted.{suffix}"
    output_path = join(parameters['output_path'], save_relative_path, name)
    if suffix.lower() in ['jpg', 'jpeg']:
        new_image = new_image.convert('RGB')

    new_image.save(output_path, quality=95, subsampling=0)

    json = {
        'width': size[0],
        'height': size[1],
        'col': parameters['col'],
        'row': parameters['row'],
        'has_password': has_password,
        'password_base64': encrypt(AES.MODE_CFB, parameters['password'], 'PASS', base64=True) if has_password else 0,
        'normal_encryption': parameters['normal_encryption'],
        'rgb_mapping': parameters['mapping'],
        'xor_rgb': parameters['xor_rgb'],
        'xor_alpha': parameters['xor_alpha'],
        'version': 2
    }

    with open(output_path, "a") as f:
        f.write('\n' + dumps(json, separators=(',', ':')))


def main():
    program = load_program()

    if program.parameters['format'] in ('jpg', 'jpeg', 'wmf', 'webp'):
        program.logger.warning('当前保存格式为有损压缩格式')
        if program.parameters['mapping']:
            program.logger.warning('在此情况下，使用RGB(A)随机映射会导致图片在解密后出现轻微的分界线，按任意键确定')
            pause()
        if program.parameters['xor_rgb']:
            program.logger.warning('在此情况下，使用异或加密会导致图片解密后出现严重失真，按任意键确定')
            pause()

    future_list = []

    if not EXTENSION:
        PIL_init()
    for relative_path, files in walk_file(program.parameters['input_path'], program.parameters['topdown']):
        save_dir = join(program.parameters['output_path'], relative_path)
        for file in files:
            path = join(program.parameters['input_path'], relative_path, file)
            '''if is_using(path):
                program.logger.warning(f'文件[{file}]正在被使用，跳过处理')
                continue'''
            if not exists(save_dir):
                makedirs(save_dir)
            name, suffix = splitext(file)
            if suffix in EXTENSION and not (name.endswith('-encrypted') or name.endswith('-decrypted')):
                future_list.append(program.process_pool.submit(encrypt_image, path, program.parameters, relative_path))

    if future_list:
        widgets = [Percentage(), ' ', SimpleProgress(), ' ', Bar('█'), ' ']
        bar = ProgressBar(max_value=len(future_list), widgets=widgets)

        for future in future_list:
            result = future.result()
            bar.update(bar.value + 1)
            if result is not None:
                program.logger.warning(f'[{result[0]}]{result[1]}')

        bar.finish()
    program.logger.info('完成')
