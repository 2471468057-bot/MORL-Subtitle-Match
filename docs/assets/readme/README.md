# README 素材来源与复现

首图为主页 PNG；五张 GIF 只演示各自功能，固定镜头，不驱动产品页滚动。转写/切分/复核/切片共用原 React 组件和状态，切分、撤销、采用、加入剪辑是真实指针点击。字幕作品保持原木刻与 CRT 美术。所有预置示例均不代表模型识别速度或准确率。

| 文件 | 内容 | 时长 / 输出 |
| --- | --- | --- |
| overview.png | 主页、素材入口与三种识别角色 | 静态 PNG |
| speaker-tracks.gif | A → B → A 逐句转写并落轨，窗口保持不动 | 8秒 / 1080px / 25fps |
| word-split.gif | 两次点击切分，轨道1→2→3段，逐次撤销 | 10秒 / 1080px / 25fps |
| candidate-review.gif | 比较候选，采用 FireRed，当前字幕人物→任务，重置 | 9秒 / 1080px / 25fps |
| live-clips.gif | 切换三种候选，理由和选区更新，加入剪辑后重置 | 11秒 / 1080px / 25fps |
| caption-effects.gif | 原木刻压印和CRT的完整入场/停留/退场 | 3.8秒 / 1080px / 25fps |
| desktop-brand.png | 新冻结 EXE 正常主窗口，隔离空配置 | 原生窗口截图 |
| 其他 PNG | 功能动图关键帧、最终Studio和术语库 | 静态替代 |

体积与 SHA256 见 [manifest.json](manifest.json)。旧17秒滚动总览已撤下。五张 GIF 使用单一全局调色板、不透明差分帧和统一40ms帧间隔，减少色彩跳变与透明帧残留。四个固定功能窗口尺寸及顶栏逐帧一致；动效只发生在文本、控件和选区内部。

## 复现

1. 准备项目已有网站依赖，运行 `node website/scripts/build-product.mjs` 与 `node website/scripts/build-readme-scenes.mjs`。
2. `node website/scripts/serve-product.mjs` 启动本机审核服务。
3. `node website/scripts/capture-readme-fixed.mjs` 以25fps时间轴逐帧采样。模块位置可用 `PLAYWRIGHT_MODULE` 传入 Playwright 文件 URL；`README_RAW` 可指定原帧目录，默认在项目tmp下。
4. `node website/scripts/render-readme-effects.mjs` 用同样25fps时钟采样原作品，循环接点遵循作品时间，不从静态停留突然跳回入场。
5. `python website/scripts/encode-readme.py` 编码GIF、静态图、原质量本地MP4与SHA清单。
6. `node website/scripts/preview-readme.mjs` 和 `node website/scripts/verify-readme.mjs` 检查本地浅/深色及390px布局。Marked模块可用 `MARKED_MODULE` 指定。

`readme.jsx/readme.css` 是独立录制入口，正式网站滚动方式不变。旧 `capture-readme.mjs` 仅保留历史录制参考，不再用于当前README。

桌面图通过 `scripts/verify_frozen_brand.py --exe <新EXE> --output <全新tmp目录>`生成；只使用 `packaged=true` 的回执。原素材没有私人媒体、用户配置、密钥或模型目录。

## 查看边界

本地预览不能替代 GitHub 目标分支线上渲染。当前修改未推送、未部署；五段新MP4交付在本地 `releases/daily-20260930/demo/`。
