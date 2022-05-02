"""
Author       : noeru_desu
Date         : 2021-11-13 10:18:16
LastEditors  : noeru_desu
LastEditTime : 2022-05-02 14:47:25
Description  : 文件载入功能
"""
from os.path import isdir, isfile, join, split
from typing import TYPE_CHECKING, Iterable, overload

from PIL import Image
from wx import ID_YES, YES_NO, CallAfter

from image_encryptor.constants import EXTENSION_KEYS, DialogReturnCodes
from image_encryptor.frame.controls import ProgressBar, Settings
from image_encryptor.frame.file_item import ImageItem, PathData
from image_encryptor.modules.image import open_image
from image_encryptor.utils.misc_utils import walk_file
from image_encryptor.utils.thread import ThreadManager

if TYPE_CHECKING:
    from os import PathLike
    from image_encryptor.frame.events import MainFrame

STOP = 2


class ImageLoader(object):
    __slots__ = (
        'frame', 'loading_thread', 'progress_plane_displayed', 'file_count', 'loading_progress',
        'clipboard_count', 'bar'
    )

    def __init__(self, frame: 'MainFrame'):
        """
        Args:
            frame (MainFrame): `MainFrame`实例
        """
        self.frame = frame
        self.loading_thread = ThreadManager('loading-thread')
        self.progress_plane_displayed = False
        self.file_count = 0
        self.loading_progress = 0
        self.clipboard_count = 0
        self.bar = None

    @overload
    def load(self, image: Image.Image) -> None:
        """加载图像

        Args:
            path_chosen (Iterable | str): 需要加载的文件路径的字符串/可迭代对象
        Args:
            image (Image): `PIL.Image.Image`实例
        """

    @overload
    def load(self, path: Iterable['PathLike[str]'] | 'PathLike[str]') -> None: ...

    def load(self, target: Iterable['PathLike[str]'] | 'PathLike[str]' | Image.Image):
        if not self.loading_thread.is_ended:
            self.frame.dialog.async_warning('请等待当前图像载入完成后再载入新的图像')
            return
        Image.MAX_IMAGE_PIXELS = self.frame.controls.max_image_pixels if self.frame.controls.max_image_pixels != 0 else None
        if not self.frame.tree_manager.file_dict:
            self.frame.set_settings_as_default()  # 当没有加载任何图像时，将当前的设置设为默认设置
        if isinstance(target, Image.Image):
            self.loading_thread.start_new(self._load_image_object, self._loading_callback, (target,))
        else:
            self.loading_thread.start_new(self._load_selected_path, self._loading_callback, (target,))

    def _loading_callback(self, error, result):
        """文件加载任务回调"""
        if error is not None:
            self.frame.dialog.async_error(repr(error))

    def _load_image_object(self, image: 'Image.Image'):
        """加载`Image`实例"""
        self.frame.loadingPanel.Disable()
        cache = True
        if self.frame.startup_parameters.low_memory:
            match self.frame.dialog.confirmation_frame('是否将该剪切板中的图像缓存在内存中?', cancel='取消载入'):
                case DialogReturnCodes.yes:
                    cache = True
                case DialogReturnCodes.no:
                    cache = False
                case _:
                    self.frame.stop_loading_func.init()
                    return
        self.clipboard_count += 1
        name = f'clipboard-{self.clipboard_count}'
        image_item = ImageItem(self.frame, image.convert('RGBA'), PathData('', '', name), no_file=True, keep_cache_loaded_image=cache)
        item_id = self.frame.tree_manager.add_file(image_item, '', '', name)
        self.frame.imageTreeCtrl.SelectItem(item_id)
        self.frame.stop_loading_func.init()

    def _load_selected_path(self, path_chosen):
        """加载文件/文件夹"""
        if isinstance(path_chosen, str):
            path_chosen = (path_chosen,)
        self.frame.loadingPanel.Disable()
        self.frame.imageTreeCtrl.Disable()
        self.frame.processingOptions.Disable()
        for i in path_chosen:
            if self.loading_thread.exit_signal:
                self.frame.stop_loading(False)
                break
            if self._exist(i):
                continue
            if isfile(i):
                self._load_file(i)
            elif isdir(i):
                if self._load_dir(i) == STOP:
                    break
        self.frame.imageTreeCtrl.Enable()
        self.frame.processingOptions.Enable()
        self.frame.loadingPanel.Enable()
        self.hide_loading_progress_plane()

    def _load_file(self, path_chosen):
        """加载文件"""
        loaded_image, error = open_image(path_chosen)
        if error is None:
            path, name = split(path_chosen)
            image_item = ImageItem(
                self.frame, None if self.frame.startup_parameters.low_memory else loaded_image, PathData(path, '', name)
            )
            item_id = self.frame.tree_manager.add_file(image_item, path_chosen)
            image_item.load_encryption_parameters()
            CallAfter(self.frame.imageTreeCtrl.SelectItem, item_id)     # 此方法在加密模式下会调用密码输入框，需回到主线程执行
        else:
            self._output_image_loading_failure_info(error)
        self.frame.stop_loading_func.init()

    def _load_dir(self, path_chosen):
        """加载文件夹"""
        self.show_loading_progress_plane()
        folder_name = split(path_chosen)[1]
        match self.frame.dialog.confirmation_frame(f'是否将文件夹{folder_name}内子文件夹中的文件也进行载入？', '选择', cancel='取消载入操作'):
            case DialogReturnCodes.yes:
                topdown = True
            case DialogReturnCodes.no:
                topdown = False
            case _:
                self.hide_loading_progress_plane()
                return
        file_num, files = walk_file(path_chosen, topdown, EXTENSION_KEYS)
        if file_num == 0:
            self.frame.dialog.async_info(f'没有从文件夹{folder_name}中载入任何文件')
            self.finish_loading_progress()
            return
        self.init_loading_progress(file_num, True)
        settings_tuple = self.frame.settings.default.properties_tuple
        loaded_num = 0
        load_failures = 0

        for r, fl in files:
            for n in fl:

                if self.loading_thread.exit_signal:
                    self.frame.stop_loading(False)
                    return STOP

                absolute_path = join(path_chosen, r, n)
                if absolute_path in self.frame.tree_manager.file_dict:
                    self.add_loading_progress()
                    continue

                loaded_image, error = open_image(absolute_path)
                if error is None:
                    image_item = ImageItem(
                        self.frame, None if self.frame.startup_parameters.low_memory else loaded_image,
                        PathData(path_chosen, r, n), Settings(self.frame.controls, settings_tuple)
                    )
                    self.frame.tree_manager.add_file(image_item, path_chosen, r, n, False)
                    image_item.load_encryption_parameters()
                    self.add_loading_progress()
                    loaded_num += 1
                else:
                    load_failures += 1
                    self._output_image_loading_failure_info(error, False, n)

        self.finish_loading_progress()
        self.frame.stop_loading_func.init()
        self.frame.dialog.async_info('成功从文件夹{}\n载入了{}个文件\n跳过了{}个文件\n失败了{}个文件'.format(
            folder_name, loaded_num, self.loading_progress - load_failures - loaded_num, load_failures
        ))

    def _output_image_loading_failure_info(self, massage: str, pop_up=True, file_name='图像'):
        """输出图像加载时出现的错误信息"""
        if pop_up:
            self.frame.dialog.async_error(massage, f'加载{file_name}时出现错误')
        else:
            self.frame.logger.warning(f'加载{file_name}时出现错误: {massage}')

    def _exist(self, path_chosen):
        """检测是否已存在于文件树"""
        if path_chosen in self.frame.tree_manager.file_dict:
            item_id = self.frame.tree_manager.file_dict[path_chosen]
        elif path_chosen in self.frame.tree_manager.root_dir_dict:
            item_id = self.frame.tree_manager.root_dir_dict[path_chosen]
            if self.frame.dialog.confirmation_frame('是否尝试从文件夹追加图像到程序中?', '请选择', YES_NO) == ID_YES:
                self.frame.imageTreeCtrl.CollapseAll()
                self.frame.imageTreeCtrl.EnsureVisible(item_id)
                self.frame.imageTreeCtrl.Expand(item_id)
                return False
        elif path_chosen in self.frame.tree_manager.dir_dict:
            item_id = self.frame.tree_manager.dir_dict[path_chosen]
            if self.frame.dialog.confirmation_frame('是否尝试从文件夹追加图像到程序中?', '请选择', YES_NO) == ID_YES:
                self.frame.imageTreeCtrl.CollapseAll()
                self.frame.imageTreeCtrl.EnsureVisible(item_id)
                self.frame.imageTreeCtrl.Expand(item_id)
                return False
        else:
            return False
        match self.frame.dialog.confirmation_frame('已存在同路径文件(夹), 是否在跳转到相应位置后重载?', '每一文件(夹)只可存在1个实例', cancel='取消操作'):
            case DialogReturnCodes.yes:
                CallAfter(self.frame.imageTreeCtrl.SelectItem, item_id)
                self.frame.imageTreeCtrl.EnsureVisible(item_id)
                self.frame.imageTreeCtrl.Expand(item_id)
                self.frame.tree_manager.reload_item(item_id)
            case DialogReturnCodes.no:
                CallAfter(self.frame.imageTreeCtrl.SelectItem, item_id)
                self.frame.imageTreeCtrl.EnsureVisible(item_id)
                self.frame.imageTreeCtrl.Expand(item_id)
        return True

    def show_loading_progress_plane(self):
        """显示加载进度信息"""
        if self.progress_plane_displayed:
            return
        self.progress_plane_displayed = True
        self.frame.loadingPanel.Hide()
        self.frame.loadingPrograssPanel.Show()

    def hide_loading_progress_plane(self):
        """隐藏加载进度信息"""
        if not self.progress_plane_displayed:
            return
        self.progress_plane_displayed = False
        self.frame.loadingPrograssPanel.Hide()
        self.frame.loadingPanel.Show()

    def init_loading_progress(self, file_count: int, use_progress_bar=False):
        """初始化加载进度信息

        Args:
            file_count (int): 需要加载的文件总数
            use_progress_bar (bool, optional): 是否使用进度条. 默认为`False`.
        """
        self.loading_progress = 0
        self.file_count = file_count
        if use_progress_bar:
            self.bar = ProgressBar(self.frame.loadingPrograss)
            self.bar.next_step(file_count)
        else:
            self.bar = None
            self.frame.loadingPrograss.SetValue(0)
        self.frame.controls.loading_prograss_info = f'0/{file_count} - 0%'

    def add_loading_progress(self):
        """增加加载进度"""
        self.loading_progress += 1
        if self.bar is not None:
            self.bar.add()
        self.frame.controls.loading_prograss_info = f"{self.loading_progress}/{self.file_count} - {format(self.loading_progress / self.file_count * 100, '.2f')}%"

    def finish_loading_progress(self):
        """完成加载进度"""
        if self.bar is not None:
            self.bar.over()
        else:
            self.frame.loadingPrograss.SetValue(100)
        self.frame.controls.loading_prograss_info = f'{self.file_count}/{self.file_count} - 100%'
