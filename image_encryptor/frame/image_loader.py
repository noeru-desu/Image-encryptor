'''
Author       : noeru_desu
Date         : 2021-11-13 10:18:16
LastEditors  : noeru_desu
LastEditTime : 2022-02-10 12:58:45
Description  : 文件载入功能
'''
from os.path import isfile, isdir, join, split
from typing import TYPE_CHECKING, Iterable

from PIL import Image
from wx import ID_YES, ID_NO, ID_CANCEL

from image_encryptor.constants import EXTENSION_KEYS
from image_encryptor.utils.utils import open_image
from image_encryptor.frame.tree_manager import ImageItem
from image_encryptor.frame.controls import ProgressBar
from image_encryptor.utils.thread import ThreadManager
from image_encryptor.utils.misc_util import walk_file

if TYPE_CHECKING:
    from image_encryptor.frame.events import MainFrame


class ImageLoader(object):
    def __init__(self, frame: 'MainFrame'):
        self.frame = frame
        self.loading_thread = ThreadManager('loading-thread')
        self.progress_plane_displayed = False
        self.file_count = 0
        self.loading_progress = 0
        self.clipboard_count = 0
        self.bar = None

    def load(self, path_chosen: Iterable | str | Image.Image):
        if not self.loading_thread.is_ended:
            self.frame.dialog.async_warning('请等待当前图片载入完成后再载入新的图片')
            return
        Image.MAX_IMAGE_PIXELS = self.frame.controls.max_image_pixels if self.frame.controls.max_image_pixels != 0 else None
        if not self.frame.tree_manager.file_dict:
            self.frame.set_settings_as_default()  # 当没有加载任何图片时，将当前的设置设为默认设置
        if isinstance(path_chosen, Image.Image):
            self.loading_thread.start_new(self._load_image_object, self._loading_callback, (path_chosen,), callback_args=(None,))
        elif isinstance(path_chosen, str):
            self.loading_thread.start_new(self._load_selected_path, self._loading_callback, (path_chosen,), callback_args=(None,))
        elif isinstance(path_chosen[0], str):
            self.loading_thread.start_new(self._load_selected_path, self._loading_callback, (path_chosen[0],), callback_args=(path_chosen[1:],))
        else:
            raise Exception(f'Unsupported type: {type(path_chosen)}')

    def _loading_callback(self, error, result, path_chosen):
        if error is not None:
            self.frame.dialog.async_error(repr(error))
        if not path_chosen:
            self.hide_loading_progress_plane()
            return
        self.loading_thread.start_new(self._load_selected_path, self._loading_callback, (path_chosen[0],), callback_args=(path_chosen[1:],))

    def _load_image_object(self, image: 'Image.Image'):
        self.frame.loadingPanel.Disable()
        if self.frame.startup_parameters.low_memory:
            result = self.frame.dialog.confirmation_frame('是否将该剪切板中的图片缓存在内存中?', cancel='取消载入')
            if result == ID_CANCEL:
                self.frame.loadingPanel.Enable()
                self.frame.stop_loading_func.init()
                return
            elif result == ID_YES:
                cache = True
            elif result == ID_NO:
                cache = False
        else:
            cache = True
        self.clipboard_count += 1
        name = f'clipboard-{self.clipboard_count}'
        image_item = ImageItem(self.frame, image.convert('RGBA'), name, self.frame.settings.default.deepcopy(), True, cache)
        self.frame.tree_manager.add_file('', '', name, image_item)
        self.frame.imageTreeCtrl.SelectItem(tuple(self.frame.tree_manager.file_dict.values())[-1])
        self.frame.loadingPanel.Enable()
        self.frame.stop_loading_func.init()

    def _load_selected_path(self, path_chosen):
        if self._exist(path_chosen):
            return
        if isfile(path_chosen):
            self._load_file(path_chosen)
        elif isdir(path_chosen):
            self._load_dir(path_chosen)

    def _load_file(self, path_chosen):
        self.frame.loadingPanel.Disable()
        loaded_image, error = open_image(path_chosen)
        if self._hint_image(error):
            path, name = split(path_chosen)
            image_item = ImageItem(
                self.frame, None if self.frame.startup_parameters.low_memory else loaded_image, (path, '', name),
                self.frame.settings.default.deepcopy()
            )
            self.frame.tree_manager.add_file(path_chosen, data=image_item)
            image_item.load_encryption_parameters()
            self.frame.imageTreeCtrl.SelectItem(tuple(self.frame.tree_manager.file_dict.values())[-1])
            image_item.check_encryption_parameters()
        self.frame.loadingPanel.Enable()
        self.frame.stop_loading_func.init()

    def _load_dir(self, path_chosen):
        self.show_loading_progress_plane()
        folder_name = split(path_chosen)[1]
        frame_id = self.frame.dialog.confirmation_frame(f'是否将文件夹{folder_name}内子文件夹中的文件也进行载入？', '选择', cancel='取消载入操作')
        if frame_id == ID_YES:
            topdown = True
        elif frame_id == ID_NO:
            topdown = False
        else:
            self.hide_loading_progress_plane()
            return
        file_num, files = walk_file(path_chosen, topdown, EXTENSION_KEYS)
        if file_num == 0:
            self.frame.dialog.async_info(f'没有从文件夹{folder_name}中载入任何文件')
            self.finish_loading_progress()
            return
        self.init_loading_progress(file_num, True)
        for r, fl in files:
            for n in fl:
                loaded_image, error = open_image(join(path_chosen, r, n))
                if self._hint_image(error, False, n):
                    image_item = ImageItem(
                        self.frame, None if self.frame.startup_parameters.low_memory else loaded_image,
                        (path_chosen, r, n), self.frame.settings.default.deepcopy()
                    )
                    self.frame.tree_manager.add_file(path_chosen, r, n, image_item, False)
                    image_item.load_encryption_parameters()
                    self.add_loading_progress()
                if self.loading_thread.exit_signal:
                    self.frame.stop_loading(False)
                    return
        self.finish_loading_progress()
        self.frame.stop_loading_func.init()
        self.frame.dialog.async_info(f'成功从文件夹{folder_name}载入了{self.loading_progress}个文件')
        self.loading_progress = 0

    def _hint_image(self, error, prompt=True, file_name='图片'):
        if error is not None:
            if prompt:
                self.frame.dialog.async_error(error, f'加载{file_name}时出现错误')
            else:
                self.frame.logger.warning(f'加载{file_name}时出现错误: {error}')
            return False
        else:
            return True

    def _exist(self, path_chosen):
        if path_chosen in self.frame.tree_manager.file_dict:
            self.frame.imageTreeCtrl.SelectItem(self.frame.tree_manager.file_dict[path_chosen])
            self.frame.imageTreeCtrl.Expand(self.frame.tree_manager.file_dict[path_chosen])
            self.frame.dialog.async_warning('已存在同路径文件\n已自动跳转到相应位置')
            return True
        elif path_chosen in self.frame.tree_manager.root_dir_dict:
            self.frame.imageTreeCtrl.SelectItem(self.frame.tree_manager.root_dir_dict[path_chosen])
            self.frame.imageTreeCtrl.Expand(self.frame.tree_manager.root_dir_dict[path_chosen])
            self.frame.dialog.async_warning('已存在同路径文件夹\n已自动跳转到相应位置')
            return True
        elif path_chosen in self.frame.tree_manager.dir_dict:
            self.frame.imageTreeCtrl.SelectItem(self.frame.tree_manager.dir_dict[path_chosen])
            self.frame.imageTreeCtrl.Expand(self.frame.tree_manager.dir_dict[path_chosen])
            self.frame.dialog.async_warning('已存在同路径文件夹\n已自动跳转到相应位置')
            return True
        else:
            return False

    def show_loading_progress_plane(self):
        if self.progress_plane_displayed:
            return
        self.progress_plane_displayed = True
        self.frame.loadingPanel.Hide()
        self.frame.loadingPrograssPanel.Show()

    def hide_loading_progress_plane(self):
        if not self.progress_plane_displayed:
            return
        self.progress_plane_displayed = False
        self.frame.loadingPrograssPanel.Hide()
        self.frame.loadingPanel.Show()

    def init_loading_progress(self, file_count, use_progress_bar=False):
        self.file_count = file_count
        if use_progress_bar:
            self.bar = ProgressBar(self.frame.loadingPrograss)
            self.bar.next_step(file_count)
        else:
            self.bar = None
            self.frame.loadingPrograss.SetValue(0)
        self.frame.controls.loading_prograss_info = f'0/{file_count} - 0%'

    def add_loading_progress(self):
        self.loading_progress += 1
        self.bar.add()
        self.frame.controls.loading_prograss_info = f"{self.loading_progress}/{self.file_count} - {format(self.loading_progress / self.file_count * 100, '.2f')}%"

    def finish_loading_progress(self):
        if self.bar is not None:
            self.bar.over()
        else:
            self.frame.loadingPrograss.SetValue(100)
        self.frame.controls.loading_prograss_info = f'{self.file_count}/{self.file_count} - 100%'
