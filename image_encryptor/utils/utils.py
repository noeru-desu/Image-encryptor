'''
Author       : noeru_desu
Date         : 2021-08-28 18:35:58
LastEditors  : noeru_desu
LastEditTime : 2021-10-09 21:22:16
Description  : 一些小工具
'''
from os import system, walk
from os.path import normpath

from Crypto.Cipher import AES
from image_encryptor.modules.version_adapter import load_encryption_attributes
from image_encryptor.utils.AES import encrypt


class fake_bar(object):
    value = 0

    def update(self, n):
        pass

    def finish(self):
        pass


def pause():
    system('pause>nul')


'''from win32file import FILE_ATTRIBUTE_NORMAL, GENERIC_READ, INVALID_HANDLE_VALUE, OPEN_EXISTING, CloseHandle, CreateFile
def is_using(path):
    return False  # 暂时禁用
    try:
        vHandle = CreateFile(path, GENERIC_READ, 0, None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
        if int(vHandle) == INVALID_HANDLE_VALUE:
            return True
        CloseHandle(vHandle)
    except Exception as e:
        print(e)
        return True'''


def walk_file(path, topdown=False):
    path = normpath(path)
    path_len = len(path) + 1
    for top, dirs, files in walk(path, topdown):
        yield top[path_len:], files


def calculate_formula_string(formula_string: str, **format):
    try:
        result = int(eval(formula_string.format(**format)))
    except SyntaxError:
        return None, '输入的公式有误，请确保输入了正确的运算符'
    except NameError:
        return None, '输入内容不为 纯数字/运算符/变量'
    except KeyError as e:
        return None, f'未知的变量：{str(e)}。当前提供：{", ".join(format.keys())}'
    except Exception as e:
        return None, f'运算输入的公式时出现错误：{repr(e)}'
    else:
        return result, None


def check_password(path, extra_info='', auto_check_password_set: set = None):
    image_data, error = load_encryption_attributes(path)
    if error is not None:
        return None, None, error
    password = 100
    password_base64 = 0
    auto_check_password_set = set() if auto_check_password_set is None else auto_check_password_set

    if image_data['has_password']:
        password = ''
        '''
        if program.parameters['password'] != 100:
            auto_check_password_set.add(base64, program.parameters['password'])
        '''
        if auto_check_password_set:
            for b, p in auto_check_password_set:
                try:
                    if b == image_data['password_base64']:
                        password = p
                        break
                except UnicodeDecodeError:
                    continue

        if password == '':
            while True:
                password = input(f'{extra_info}需要解密的图片被密码保护，请输入密码：\n')
                if password == '':
                    continue

                try:
                    password_base64 = encrypt(AES.MODE_CFB, password, 'PASS', base64=True)
                    if password_base64 == image_data['password_base64']:
                        break
                    else:
                        print('密码错误！', end='')
                except UnicodeDecodeError:
                    print('密码错误！', end='')

    image_data['password'] = password
    return image_data, password_base64, None
