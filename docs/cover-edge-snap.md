# 封面图片边框吸附

封面编辑器底部增加「边框吸附：关闭 / 开启」按钮。默认关闭，状态仅在本次编辑器窗口内有效，不改变封面文件格式或用户设置。

开启后，单张未锁定图片的矩形外框可以吸附到画布对应的四边。进入距离为 8 个视口逻辑像素，超过 12 个逻辑像素脱离，避免边界附近抖动。画布缩放参与换算；大于画布的图片仍可保持负坐标。拖远或按住 Alt 后继续移动即可自由越界裁切。透明边缘按整张图片的矩形计算。

文字、多选、缩放手柄、键盘微调和属性输入沿用原行为。一次拖动仍对应原有的一次撤销；辅助线只在画布前景绘制，不进入 PNG/JPEG/PSD 内容。

## 接入与移除

- `twobyteasr/cover_snap/geometry.py`：仅依赖 Python 标准库，按轴计算坐标与对齐边。
- `twobyteasr/cover_snap/qt.py`：按钮、手势、临时辅助线；`install(view, controls)` 返回控制器，`detach()` 移除按钮与接入引用，保留当前图层位置。
- `cover_canvas.py`：默认 `drag_constraint = None`，提供位置预处理、手势开始/结束、修饰键和前景绘制接入点。
- `cover_editor.py`：可选加载模块并添加按钮。整个 `cover_snap` 包不提供时，编辑器继续使用原拖动逻辑；模块内部依赖错误不会被当成「未安装」而吞掉。

模块不是未经修改宿主即可加载的通用插件。宿主有 23 行接入；不使用动态 monkey patch，不建立插件管理平台。将此改动移植到其他版本前，应先核对以上两个宿主文件。分发可不包含可选包；运行时可调用控制器的 `detach()`。

## 本地试用

在已有 PySide6 6.9.2、QtAwesome 1.4.0 的开发 Python 中运行：

```powershell
python scripts/preview_cover_snap.py
```

打开的是真实 Qt 封面编辑器，带一张示例图片。可以添加自己的图片、拖动、切换吸附、按 Alt 和撤销重做。该入口为每次启动建立新的 `tmp/cover-snap-preview/` 数据目录，隔离配置、草稿与模板，不打开正在使用的 Studio 项目。手动选择的保存/导出路径由使用者控制。

测试使用 pytest、Pillow 和 NumPy。依照仓库已有隔离入口运行，每次使用新的测试输出目录：

```powershell
python scripts/isolated_pytest.py tests/test_cover_snap_geometry.py tests/test_cover_snap_qt.py
python scripts/isolated_pytest.py tests/test_cover_editor.py
```

提交前还应运行仓库完整测试入口 run_tests.bat。本模块不引入新的运行时依赖；安装包构建和其他平台验证沿用原项目流程。
