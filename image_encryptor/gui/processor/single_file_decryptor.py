'''
Author       : noeru_desu
Date         : 2021-09-25 20:45:37
LastEditors  : noeru_desu
LastEditTime : 2021-10-26 21:32:38
Description  : 单文件解密功能
'''
from os.path import join, split, splitext

from PIL import Image

from image_encryptor.common.modules.image_encrypt import ImageEncrypt
from image_encryptor.gui.modules.loader import load_program
from image_encryptor.gui.modules.password_verifier import get_image_data
from image_encryptor.gui.utils.utils import ProgressBar


def main(frame, logger, gauge, image: Image.Image, save: bool):
    program = load_program()

    image_data, error = get_image_data(program.data.loaded_image_path, password_dict=program.password_dict)
    if error is not None:
        frame.error(error, '读取加密参数时出现问题')
        return program.data.preview_original_image, save
    image_encrypt = ImageEncrypt(image, image_data['row'], image_data['col'], image_data['password'])
    logger('正在处理')

    step_count = 0
    if image_data['normal_encryption']:
        step_count += 2
    if image_data['xor_rgb']:
        step_count += 1
    if save:
        step_count += 1

    bar = ProgressBar(gauge, step_count)

    if image_data['normal_encryption']:
        bar.next_step(image_data['col'] * image_data['row'])
        logger('正在分割加密图像')
        image_encrypt.init_block_data(image, True, bar)

        logger('正在重组')

        bar.next_step(image_data['col'] * image_data['row'])
        image = image_encrypt.get_image(image, image_data['rgb_mapping'], bar)

    if image_data['xor_rgb']:
        logger('正在异或解密')
        bar.next_step(1)
        image = image_encrypt.xor_pixels(image, image_data['xor_alpha'])

        image = image.crop((0, 0, int(image_data['width']), int(image_data['height'])))
        bar.finish()

    if save:
        bar.next_step(1)
        logger('正在保存文件')
        name, suffix = splitext(split(program.data.loaded_image_path)[1])
        suffix = Image.EXTENSION_KEYS[frame.selectFormat.Selection]
        suffix = suffix.strip('.')
        if suffix.lower() in ['jpg', 'jpeg']:
            image = image.convert('RGB')
        name = f"{name.replace('-encrypted', '')}-decrypted.{suffix}"

        image.save(join(frame.selectSavePath.Path, name), quality=frame.saveQuality.Value, subsampling=frame.subsamplingLevel.Value)
        bar.finish()
    bar.over()
    logger('完成')
    return image, save