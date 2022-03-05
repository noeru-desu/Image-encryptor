"""
Author       : noeru_desu
Date         : 2021-10-22 18:15:34
LastEditors  : noeru_desu
LastEditTime : 2022-03-05 10:28:52
Description  : 覆写窗口
"""
from concurrent.futures import ThreadPoolExecutor
from functools import cached_property
from inspect import isroutine
from multiprocessing import cpu_count
from os import getcwd
from sys import version
from typing import TYPE_CHECKING

from image_encryptor.constants import (BRANCH, EXTENSION_KEYS_STRING,
                                       OPEN_SOURCE_URL, SUB_VERSION_NUMBER,
                                       VERSION_BATCH, VERSION_NUMBER,
                                       VERSION_TYPE)
from image_encryptor.frame.controls import Controls, SegmentTrigger, SettingsManager, Settings
from image_encryptor.frame.design_frame import MainFrame as MF
from image_encryptor.frame.dialog import Dialog
from image_encryptor.frame.drag_importer import DragLoader, DragSavingPath
from image_encryptor.frame.preview_generator import PreviewGenerator
from image_encryptor.frame.image_loader import ImageLoader
from image_encryptor.frame.image_saver import ImageSaver
from image_encryptor.frame.tree_manager import TreeManager
from image_encryptor.modules.password_verifier import PasswordDict
from image_encryptor.utils.exit_processor import ExitProcessor
from image_encryptor.utils.logger import Logger
from image_encryptor.utils.thread import ProcessTaskManager
from wx import App
from wx.core import EmptyString

# from image_encryptor.utils.misc_util import gen_slots_str

if TYPE_CHECKING:
    from image_encryptor.frame.tree_manager import ImageItem
    from image_encryptor.modules.argparse import Parameters


class MainFrame(MF):
    """
    主窗口类
    """
    __slots__ = (
        'startup_parameters', 'logger', 'controls', 'settings', 'dialog', 'universal_thread_pool',
        'password_dict', 'exit_processor', 'process_pool', 'tree_manager', 'image_loader', 'preview_generator',
        'image_saver', 'stop_loading_func', 'stop_reloading_func', 'exit_processor'
    )

    def __init__(self, parent, startup_parameters: 'Parameters', run_path=getcwd()):
        # o_args = set(dir(self))
        super().__init__(parent)
        # n_args = set(dir(self))
        # gen_slots_str(n_args - o_args)
        if VERSION_TYPE > 0:
            self.SetTitle(f'Image Encryptor GUI {VERSION_NUMBER}-{SUB_VERSION_NUMBER} (branch: {BRANCH})')
        else:
            self.SetTitle(f'Image Encryptor GUI {VERSION_NUMBER}')

        # 组件
        if startup_parameters.dark_mode:
            self.dark_mode()
        self.startup_parameters = startup_parameters
        self.logger = Logger('image-encryptor')
        self.logger.info(f'Python {version}')
        self.logger.info(f'You are using Image encryptor GUI {VERSION_NUMBER}-{SUB_VERSION_NUMBER} (branch: {BRANCH}) (batch: {VERSION_BATCH})')
        self.logger.info(f'Open source at {OPEN_SOURCE_URL}')
        self.controls = Controls(self)
        self.settings = SettingsManager(self.controls)
        self.dialog = Dialog(self)
        self.universal_thread_pool = ThreadPoolExecutor(8, 'universal_thread_pool')
        self.password_dict = PasswordDict()
        self.exit_processor = ExitProcessor()
        self.process_pool = ProcessTaskManager(1 if cpu_count() < 4 else cpu_count() - 2)
        self.tree_manager = TreeManager(self, self.imageTreeCtrl, '已加载文件列表')
        self.image_loader = ImageLoader(self)
        self.preview_generator = PreviewGenerator(self)
        self.image_saver = ImageSaver(self)
        self.imageTreeCtrl.SetDropTarget(DragLoader(self))
        self.savingOptions.SetDropTarget(DragSavingPath(self))
        self.stop_loading_func = SegmentTrigger((self.set_stop_loading_signal, self.stop_loading), self.init_loading_btn)
        self.stop_reloading_func = SegmentTrigger((self.set_reloading_btn_text, self.set_stop_reloading_signal, self.stop_reloading), self.init_reloading_btn)
        self.exit_processor.register(self.process_pool.shutdown, wait=False, cancel_futures=True)
        self.exit_processor.register(self.universal_thread_pool.shutdown, wait=False, cancel_futures=True)

        # 准备工作
        self.run_path = run_path
        self.xorPanel.Disable()
        self.savingFormat.ToolTip = f'{self.savingFormat.GetToolTipText()}{EXTENSION_KEYS_STRING}'
        self.controls.redundant_cache_length = self.startup_parameters.maximum_redundant_cache_length
        self.controls.low_memory_mode = self.startup_parameters.low_memory

        self.image_item: 'ImageItem' = None

        self.logger.info('窗口初始化完成')

    @cached_property
    def get_frame_items(self):
        for i in set(dir(self)) - set(dir(MF)):
            target = getattr(self, i)
            if not isroutine(target) and hasattr(target, 'SetBackgroundColour'):
                yield target

    def dark_mode(self):
        self.SetBackgroundColour('Dark Grey')
        for i in self.get_frame_items:
            i.SetBackgroundColour('Dark Grey')
            i.SetForegroundColour('White')

    @classmethod
    def run(cls, path=getcwd()):
        app = App(useBestVisual=True)
        self = cls(None, path)

        self.Show()

        app.MainLoop()

    def add_password_dict(self, password, dialog_parent=...):
        """添加成功则返回True"""
        try:
            self.password_dict[self.password_dict.get_validation_field_base64(password)] = password
            self.password_dict[self.password_dict.get_validation_field_base64(password, False)] = password
        except ValueError:
            self.dialog.async_error('密码长度超过AES加密限制, 请确保密码长度不超过32字节', '用于验证密码正确性的字符串生成时出现错误', parent=dialog_parent)
            return False
        else:
            return True

    def init_loading_btn(self):
        self.controls.loading_prograss = 0
        self.controls.loading_prograss_info = EmptyString
        self.controls.stop_loading_btn_text = '停止载入'

    def stop_loading(self, force=True):
        if force:
            self.image_loader.loading_thread.kill()
            self.image_loader.hide_loading_progress_plane()
            self.dialog.async_warning('已强制终止载入文件')
        else:
            self.dialog.async_warning('已停止载入文件')
        self.stop_loading_func.init()

    def set_stop_loading_signal(self):
        self.image_loader.loading_thread.set_exit_signal()
        self.controls.stop_loading_btn_text = '强制终止载入'

    def init_reloading_btn(self):
        self.controls.reloading_btn_text = '重载此项'

    def set_reloading_btn_text(self):
        self.controls.reloading_btn_text = '停止重载'

    def stop_reloading(self, force=True):
        if force:
            self.tree_manager.reloading_thread.kill()
            self.dialog.async_warning('已强制终止重载操作')
        else:
            self.dialog.async_warning('已停止重载操作')
        self.stop_loading_func.init()

    def set_stop_reloading_signal(self):
        self.tree_manager.reloading_thread.set_exit_signal()
        self.controls.stop_loading_btn_text = '强制终止重载'

    def apply_settings_to_all(self, settings_list=None):
        if settings_list is None:
            properties_tuple = self.settings.all.properties_tuple
            for i in self.tree_manager.all_image_item_data:
                i.settings = Settings(self.controls, properties_tuple)
        else:
            settings = ((i, getattr(self.image_item, i)) for i in settings_list)
            for i in self.tree_manager.all_image_item_data:
                for n, v in settings:
                    setattr(i, n, v)
