'''
Author       : noeru_desu
Date         : 2021-11-13 21:43:57
LastEditors  : noeru_desu
LastEditTime : 2021-11-13 21:56:21
Description  : 图片生成功能
'''
from typing import TYPE_CHECKING

import image_encryptor.gui.processor.qq_anti_harmony as qq_anti_harmony
import image_encryptor.gui.processor.single_file_decryptor as single_file_decryptor
import image_encryptor.gui.processor.single_file_encryptor as single_file_encryptor
from image_encryptor.gui.utils.thread import ThreadManager

if TYPE_CHECKING:
    from image_encryptor.gui.frame.main_frame import MainFrame


class ImageGenerator(object):
    def __init__(self, frame: 'MainFrame'):
        self.frame = frame
        self.preview_thread = ThreadManager('preview-thread', True)

    def generate_preview(self):
        if self.frame.update_password_dict():
            self.frame.password.SetValue('none')
        if self.frame.mode.Selection == 0:
            self.preview_thread.start_new(single_file_encryptor.main, self.generate_preview_call_back, (self, self.frame.previewProgressPrompt.SetLabelText, self.frame.previewProgress, self.frame.initial_preview, False))
        elif self.frame.mode.Selection == 1:
            self.preview_thread.start_new(single_file_decryptor.main, self.generate_preview_call_back, (self, self.frame.previewProgressPrompt.SetLabelText, self.frame.previewProgress, self.frame.loaded_image, False))
        else:
            self.preview_thread.start_new(qq_anti_harmony.main, self.generate_preview_call_back, (self, self.frame.previewProgressPrompt.SetLabelText, self.frame.previewProgress, self.frame.initial_preview, False))

    def generate_preview_call_back(self, error, image):
        if error is not None:
            self.frame.error(repr(error), '生成加密图片时出现意外错误')
            return
        self.frame.show_processing_preview(True, image)

    def save_image(self):
        if self.frame.update_password_dict():
            self.frame.password.SetValue('none')
        if self.frame.mode.Selection == 0:
            self.preview_thread.start_new(single_file_encryptor.main, self.save_image_call_back, (self, self.frame.saveProgressPrompt.SetLabelText, self.frame.saveProgress, self.frame.loaded_image, True))
        elif self.frame.mode.Selection == 1:
            self.preview_thread.start_new(single_file_decryptor.main, self.save_image_call_back, (self, self.frame.saveProgressPrompt.SetLabelText, self.frame.saveProgress, self.frame.loaded_image, True))
        else:
            self.preview_thread.start_new(qq_anti_harmony.main, self.save_image_call_back, (self, self.frame.saveProgressPrompt.SetLabelText, self.frame.saveProgress, self.frame.loaded_image, True))

    def save_image_call_back(self, error, image):
        if error is not None:
            self.frame.error(repr(error), '生成加密图片时出现意外错误')
            return
        self.frame.show_processing_preview(True, image)