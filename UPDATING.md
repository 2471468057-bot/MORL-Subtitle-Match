# 更新与版本策略

## 用户如何更新

1. 关闭正在运行的 2ByteASR。
2. 从 GitHub Releases 下载更高版本的 `2ByteASR-Setup-<版本>.exe`。
3. 直接运行安装器，不要先卸载旧版本。

安装器使用固定的 `AppId` 和安装目录，因此会原地覆盖程序文件，同时保留：

- `models/` 中已经下载的模型；
- `.venv-main/`、`.venv-moss/` 环境；
- `third_party/` 固定版本源码；
- 用户的 `twobyteasr_settings.json`、`game_profiles.json` 和 `glossary.txt`；
- `%LOCALAPPDATA%\2ByteASR` 中的加密密钥、缓存、日志和声纹。

升级后的首次配置仍会运行完整性检查。`download_models.ps1` 按模型逐个比较固定 revision 和安全关键文件的 SHA-256：未变化的模型直接跳过；只更新了一个模型时，只下载该模型。不要为了更新先卸载旧版，因为卸载操作会删除安装目录中的模型和 Python 环境。

## 维护者如何稳定发布

采用语义化版本：

- `0.1.1`：字幕规则、错误修复、文档等兼容更新；
- `0.2.0`：新增功能或有明显行为变化，但保留用户数据；
- `1.0.0`：稳定公开版；以后破坏兼容性才升级主版本。

代码更新不要修改以下稳定标识：

- `installer/2ByteASR.iss` 中的 `AppId`；
- 默认安装目录；
- `dependencies.lock.json` 中未变化模型的 key、path 和 revision。

发布补丁版示例：

```powershell
git switch main
git pull --ff-only
.\.venv-main\Scripts\python.exe -m pytest -q tests
.\.venv-main\Scripts\python.exe scripts\check_release_hygiene.py
git tag -a v0.1.1 -m "2ByteASR 0.1.1"
git push origin main
git push origin v0.1.1
```

推送 `v*` 标签后，GitHub Actions 会重新测试、构建小型安装包和 SHA-256 文件，并创建 Release。用户只需下载新的安装包；模型不会打进 Release。

## 模型更新规则

只有确实需要更新模型时，才修改对应模型的：

- `revision`；
- 安全关键文件 `sha256`；
- 必要时的 `required_files`。

一次 Release 尽量只改变一个大模型，并在发行说明中明确预计新增下载量。不要把所有模型 revision 统一刷新到“最新”，否则用户会发生不必要的大规模下载。

## 发布前升级测试

每个 Release 至少验证：

1. 空目录首次安装；
2. 在上一稳定版上直接覆盖安装；
3. 用户设置、词表和模型目录仍存在；
4. 未变化模型显示“跳过”；
5. 卸载仅用于彻底删除，不作为升级步骤；
6. 安装包 SHA-256 与 Release 附件一致；有证书时验证 Authenticode 签名。
