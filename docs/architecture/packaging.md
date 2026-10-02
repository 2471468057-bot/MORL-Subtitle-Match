# 0.5.0 源码与桌面分发边界

项目自有代码采用 GPL-3.0-only，第三方原许可与版权保留。

有限源码 C 包含明确选择的可编辑程序、接口、构建脚本、锁文件和必要声明；预编译运行环境、模型缓存、私人历史/任务、独立品牌原件不在该范围。C 与实际 Windows/Mac 构建输入不同，也不是两平台完整应用的全部对应源码。

Windows 封存修复 Setup 与配对源码/材料保持原身份。Mac 的实际构建输入固定 cfe9b13dafa7c4aa068034a7a9fd9fcf601c6f1b，原生应用为 Apple Silicon arm64 实验版，已验证 SenseVoice CPU 主流程，仅 ad hoc 签名。现有 renderer 与 AAC 运行链保持。

仓库当前 main 的普通追加更新不清除旧 Git 历史；正式公开根的历史与 refs 范围另行确认。保留的旧 CI/release YAML 仅为私有 main 的原工作流记录，拟公开 C 单根树排除它们；本轮不添加或触发新构建。既有手动 Mac workflow 保留原源码范围。

[源码边界](../../SOURCE_ONLY_SCOPE.md) · [源码交付](../../SOURCE_DELIVERY.md) · [Mac 构建](../deployment/macos-build.zh-CN.md)
