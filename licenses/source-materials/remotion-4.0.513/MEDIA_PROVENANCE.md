# 媒体输入来源事实（项目自写说明）

此文件说明内部取证到的版本链，不复制第三方实现，不是完整构建配方，也不授予媒体库分发权。

- Remotion compositor版本4.0.513的Cargo锁指定rust-ffmpeg-sys e20f3b7d15db0386e1ab62cb107ca6bab0cd79ae。
- 该sys提交的[来源记录](https://github.com/remotion-dev/rust-ffmpeg-sys/blob/e20f3b7d15db0386e1ab62cb107ca6bab0cd79ae/zips/SOURCE.md)指向splitter 39ddfbb2283857327c5f31635059c399eaab7b4c。Windows x64 GNU来自CircleCI pipeline444/workflow ce0af6ed-51a2-4937-83a5-230e0d27a8ce；不要把macOS运行记录当作Windows构建。
- 对应[Windows归档](https://raw.githubusercontent.com/remotion-dev/rust-ffmpeg-sys/e20f3b7d15db0386e1ab62cb107ca6bab0cd79ae/zips/x86_64-pc-windows-gnu.gz)SHA256 5ce7b6e6d6fa49aac970d9121368cf7942f43bd6dfacb13e2bb98a8f01e88489；16件媒体二进制与内部test.4载荷相同。本独立源码范围不提供这些二进制。
- 原来源记录SHA256 2a66becac825cc75be3e9e248448bb6ec22130d609b65e7df4367b04d8625464，内部保留原件；此文件不冒称上游原文。
- 39ddfbb整体授权未找到；20件相同字节另从明确GPL固定50b6a0c0提供，见splitter-licensed/PROVENANCE.json。9件不同旧文件未附；不能把这部分资料称为完整原生媒体构建输入。
- FFmpeg n7.1、x264/x265和FDK分别适用各自许可。脚本的GPL声明不解决FDK混合二进制权利。
