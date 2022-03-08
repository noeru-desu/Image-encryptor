"""
Author       : noeru_desu
Date         : 2021-09-25 20:45:37
LastEditors  : noeru_desu
LastEditTime : 2022-03-07 10:12:29
Description  : 单文件解密功能
"""
from os import makedirs
from os.path import isdir, join, split, splitext
from traceback import format_exc
from typing import TYPE_CHECKING

from PIL import Image

from image_encryptor.frame.controls import (EncryptionParametersData,
                                            ProgressBar, SavingSettings)
from image_encryptor.modules.image_encrypt import ImageDecrypt

if TYPE_CHECKING:
    from image_encryptor.frame.events import MainFrame
    from image_encryptor.frame.file_item import PathData


def normal(frame: 'MainFrame', logger, gauge, image: 'Image', save: bool):
    try:
        return False, _normal(frame, logger, gauge, image, save)
    except Exception:
        return True, format_exc()


def batch(image_data, path_data, encryption_data, saving_settings, auto_folder):
    try:
        return False, _batch(image_data, path_data, EncryptionParametersData(encryption_data), SavingSettings(*saving_settings), auto_folder)
    except Exception:
        return True, format_exc()


def _normal(frame: 'MainFrame', logger, gauge, image, save):
    encryption_data = frame.image_item.cache.encryption_data
    if encryption_data.has_password:
        if encryption_data.password is None:
            encryption_data.password = frame.password_dict.get_password(encryption_data.password_base64)
            if encryption_data.password is None:
                frame.dialog.async_warning('密码字典中不存在此图片的密码，请输入密码')
                return image
            else:
                password = encryption_data.password
        else:
            password = encryption_data.password
    else:
        password = 100
    image_decrypt = ImageDecrypt(image, encryption_data.cutting_row, encryption_data.cutting_col, password, encryption_data.version)
    logger('正在处理')

    step_count = 0
    if encryption_data.shuffle_chunks or encryption_data.flip_chunks or encryption_data.mapping_channels:
        step_count += 2
    if encryption_data.XOR_channels:
        step_count += 1
    if save:
        step_count += 1

    bar = ProgressBar(gauge, step_count)

    if encryption_data.XOR_channels:
        logger('正在异或解密')
        bar.next_step(1)
        image = image_decrypt.xor_pixels(encryption_data.XOR_channels, encryption_data.noise_XOR, encryption_data.noise_factor)

    if encryption_data.shuffle_chunks or encryption_data.flip_chunks or encryption_data.mapping_channels:
        bar.next_step(encryption_data.cutting_col * encryption_data.cutting_row)
        logger('正在分割加密图像')
        image_decrypt.init_block_data(encryption_data.shuffle_chunks, encryption_data.flip_chunks, encryption_data.mapping_channels, bar)

        logger('正在重组')

        bar.next_step(encryption_data.cutting_col * encryption_data.cutting_row)
        image = image_decrypt.generate_image(bar)

    image = image.crop((0, 0, int(encryption_data.orig_width), int(encryption_data.orig_height)))

    if save:
        bar.next_step(1)
        logger('正在保存文件')
        name, suffix = splitext(split(frame.image_item.loaded_image_path)[1])
        suffix = frame.controls.saving_format
        if suffix.lower() in ('jpg', 'jpeg'):
            image = image.convert('RGB')
        name = f"{name.replace('-encrypted', '')}-decrypted.{suffix}"

        image.save(join(frame.controls.saving_path, name), quality=frame.controls.saving_quality, subsampling=frame.controls.saving_subsampling_level)
        bar.finish()
    bar.over()
    logger('完成')
    return image


def _batch(image_data, path_data: 'PathData', encryption_data: 'EncryptionParametersData', saving_settings: 'SavingSettings', auto_folder):
    image = Image.frombytes(*image_data)
    image_decrypt = ImageDecrypt(image, encryption_data.cutting_row, encryption_data.cutting_col, encryption_data.password if encryption_data.has_password else 100, encryption_data.version)

    if encryption_data.XOR_channels:
        image = image_decrypt.xor_pixels(encryption_data.XOR_channels, encryption_data.noise_XOR, encryption_data.noise_factor)

    if encryption_data.shuffle_chunks or encryption_data.flip_chunks or encryption_data.mapping_channels:
        image_decrypt.init_block_data(encryption_data.shuffle_chunks, encryption_data.flip_chunks, encryption_data.mapping_channels)
        image = image_decrypt.generate_image()

    image = image.crop((0, 0, int(encryption_data.orig_width), int(encryption_data.orig_height)))

    name, suffix = splitext(path_data.file_name)
    suffix = saving_settings.format
    if suffix.lower() in ('jpg', 'jpeg'):
        image = image.convert('RGB')
    name = f"{name.replace('-encrypted', '')}-decrypted.{suffix}"
    if auto_folder:
        save_dir = join(saving_settings.path, path_data.relative_path)
        if not isdir(save_dir):
            makedirs(save_dir)
    else:
        save_dir = saving_settings.path

    image.save(join(save_dir, name), quality=saving_settings.quality, subsampling=saving_settings.subsampling_level)
