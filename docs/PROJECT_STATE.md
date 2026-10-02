# 0.5.0 当前产品状态

2026-10-02：Windows 修复版及 macOS Apple Silicon 实验版的首轮 SenseVoice CPU 主流程验证已结束。Windows 已验证无密钥中文识别、字幕编辑/剪切/撤销重做/保存重开、四格式字幕和短视频导出；Mac 已生成实际 arm64 应用并验证冷模型准备、正常启动、可见视频与中文编辑、字幕/短视频导出及新媒体重启任务。

当前尚无公开安装包。原仓库保持 private，0.5.0 Release 保持 draft/prerelease，附件仅用于作者受控的私有准备。完整应用的公开分发条件与独立源码范围分别记录，不把功能验证等同权利或全部对应源码完备。

Mac 仅 ad hoc 签名，未作 Developer ID 签名/公证；Intel、整模型 MPS、物理输入法、人工听感、所有长任务未验证。Docker 产品方向已撤下，现有功能不因此删改。

[三语产品入口](../README.md) · [Mac 状态](deployment/macos-validation.zh-CN.md) · [独立源码范围](../SOURCE_ONLY_SCOPE.md) · [交付说明](../SOURCE_DELIVERY.md)
