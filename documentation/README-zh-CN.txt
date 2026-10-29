VBA-RR v24.1 中文版（HD2）
==========================

本项目以本地 VBA-RR v24.1 / v8 核心源码为基础，恢复并补充中文界面，增加
Lua UTF-8 中文绘字与高清 HUD。它不是原 v24m-svn480+LRC4 二进制的完整还原，
不据此保证核心时序、LRC4 功能或旧录像完全等价。

使用发布包
----------
运行 VBA-rr-zh.exe。lua51.dll 和 lua5.1.dll 必须与 EXE 同目录。
发布包不附带测试 Lua 脚本。开发用示例仅保留在源码的 examples/lua/。
这是 Win32/x86 构建，以 Windows 7 及以上为目标，未验证 Windows XP。

文字模式默认“游戏内”，已有配置优先。三种文字显示模式均保留高清字体。
高清文字在游戏滤镜之后合成，暂停时保留，DirectDraw/GDI 在后台完成合成后
一次提交画面。建议使用3倍窗口；小窗口和非整数缩放的字形细节会受到像素数限制。
“游戏内”模式的菜单截图/AVI 仍按游戏原始分辨率输出，高清层在临时录制帧中
缩小合成，不会写回实时游戏缓冲。其他显示模式的截图/AVI 不包含高清层。
本轮整理和打包未启动模拟器，实际运行验收由发布者完成。

Lua 接口与脚本
--------------
脚本保存为 UTF-8、无 BOM。

    gui.texthd(1, 1, "模式：宝可梦信息", "white", "black", 12, nil, 2)

参数依次为：x、y、UTF-8 文本、文字色、描边色、原生字号、字体名、描边档位、
可选底衬色、可选最大宽度。坐标和最大宽度以原始游戏像素计。
默认原生12px字体在3倍画布中以2倍绘制，保持原脚本约8px的逻辑占位。
默认字体内嵌 Fusion Pixel 2026.10.25 简体中文等宽8px/12px版本，无需安装。
字体资源、上游来源与校验值位于 fonts/fusion-pixel/manifest.json。

描边档位：0关闭、1右下阴影、2细边（默认）、3完整边。
底衬默认透明；颜色使用 #RRGGBBAA，AA 越小越透明。
兼容接口 gui.textutf8 使用原始低分辨率画布；gui.text 的纯 ASCII 调用沿用
原字库，含中文时自动使用高清接口。gui.texthdversion=2 可检测当前高清接口。
Lua 5.1 的字符串库、控制台和整个 MBCS 前端并未因此全面改为 Unicode。

源码中的 RNG 测试示例顶部可修改：
    HUD_FONT_SIZE = 12
    HUD_OUTLINE_STYLE = 2
    HUD_BACKGROUND = "clear"        -- 默认无底衬
    -- "#00000040" 约25%不透明，"#00000080" 约50%不透明

脚本只翻译显示标签和说明；英文 mode/infoMode 键、内存地址与 RNG 计算保留。
宝可梦种类、招式、特性和道具等原始英文数据表保留。脚本按栏裁切长文本，
为 PP、底部帮助与 TID/SID 留出空间。底衬可自行开启。

从源码构建与打包
----------------
需要 Python 3.9+、PowerShell、Visual Studio 2022 C++ Build Tools（v143）、
对应的 x86 MFC/ATL 组件，以及 Windows SDK 10.0.22621.0。
当前构建环境使用 MSVC 14.43.34808。发布工具仅依赖 Python 标准库。
Git 检出目录需要 Git；源码包附带 SOURCE-INFO.json 和 SOURCE-FILES.sha256，
没有 .git 目录时也能构建，并保留对应的版本与源码清单。

在仓库根目录 PowerShell 执行：
    & .\tools\build_zh.ps1

需要完整重编时：
    & .\tools\build_zh.ps1 -Rebuild

输出：
    dist/VBA-rr-v24.1-zh-HD2-win32/       可直接运行的目录
    dist/VBA-rr-v24.1-zh-HD2-win32.zip    二进制发布包
    dist/VBA-rr-v24.1-zh-HD2-source.zip   对应源码快照
    dist/SHA256SUMS.txt                 两个压缩包的 SHA-256

documentation/build-info.json 记录基准提交、工作区是否有修改、源码清单哈希和 EXE 哈希。
二进制包按原版规格组织：顶层仅 EXE、两个 Lua DLL 和 documentation/；
历史变更记录、Lua 文档、中文说明与附加许可证均位于 documentation/。
提交代码后重新运行构建命令，生成带该提交号的最终发布包。
源码包包含 Git 管理的文件与未忽略的新文件，不依赖本机旧汉化程序目录。
二进制包按固定清单收集，不会从运行目录打包 vba.ini、ROM、存档或日志。
重新打包会先把同名运行目录完整保留到 .userdata/package-replaced/，
再生成干净目录，避免遗留之前附带的脚本；该备份目录被 Git 忽略。
如只重新打包现有 EXE，可用 python tools/package_release.py；改动 C++ 后应先构建。

如果本机 MFC 安装未完成，可使用 tools/fetch_mfc.py 从本机 VS 组件清单中
指定的微软地址恢复固定14.43组件，验证完整 SHA-256 后提取到 build/dependencies。
它是特殊环境的恢复工具；正常安装 MFC 的机器不需要这份缓存。
字体 OTF 已随源码提供，正常构建不需要 Python 字体库或下载字体。
重新从上游 WOFF2 包生成字体时，先安装：
    python -m pip install --target build/dependencies/font-tools fonttools brotli
再将 manifest 中指定的上游 ZIP 放入 build/dependencies/fusion-pixel，执行：
    python tools/prepare_fusion_fonts.py

GitHub Actions 自动构建与发布
----------------------------
.github/workflows/windows-release.yml 使用 windows-2022 执行相同的完整构建命令。
无需提交本机 build、dist 或 MFC 缓存；托管运行器已安装 v143、MFC/ATL 与所需 SDK。
Lua 引擎接口和绘字修改随模拟器编译。Lua 5.1 运行时沿用仓库 win32/lib/ 中
现有的 x86 lua51.dll 与 lua5.1.dll，流水线复制这两个文件，不重新编译 Lua DLL。
两个 DLL 必须一同提供；独立 DLL 不妨碍自动构建，也不要求附带任何 .lua 脚本。

普通分支 push、pull_request 或 Actions 页手动运行：
    编译资源、完整构建、验证 ZIP 内容和源码哈希，然后上传下载产物。
    在本次运行页面的 Artifacts 下载 vba-rr-win32-<提交SHA>；保存14天。
    非标签构建名包含 g<短提交号>；不会创建 GitHub Release。

推送 v 开头的版本标签：
    构建成功后自动创建 GitHub Release，附带二进制 ZIP、源码 ZIP 和 SHA256SUMS.txt。
    例如，先提交并推送代码，再执行：
        git tag v24.1-zh-HD2
        git push origin v24.1-zh-HD2
    请在手动运行验收后推送正式标签；标签名须仅含字母、数字、点、下划线、横线。
    同一标签重跑会更新已有 Release 附件，保留现有发布说明。

工作流使用仓库自动提供的 GITHUB_TOKEN，无需另设个人 Token。
只有标签发布任务请求 contents: write；编译任务保持 contents: read。
Actions 必须在目标 GitHub 仓库中启用，仓库策略需要允许工作流发布 Release。
Actions 不启动模拟器；运行验收仍由发布者完成。首次云端执行需提交推送后确认结果。

源码维护与本地文件
------------------
localization/reference-zh.json 保存原汉化资源快照；zh-CN-ui.json、
zh-CN-strings.json 和 rng-overlay-zh-CN.json 保存维护词表。
python tools/restore_zh_resources.py --apply 从已提交的资源快照重新生成译文；
--reference-exe PATH 可显式读取新的参考 EXE。不要把个人参考程序提交到仓库。

.local/reference 保存本机原始 EXE/ZIP，.local/cleanup-20261029 保存整理时归档
的旧构建和临时产物；本机迁移记录同样留在 .local 中。build、dist 和 .local
均被 Git 忽略。旧版电池存档、配置和脚本另存于 .userdata/recovered-20261029/，
该目录也被忽略，应保留。清理 .local 不会删除这些备份，Downloads 原始 ZIP 保留。
保留的 MFC 缓存仅用于本机构建，不放入源码包或发布包。
仓库原有的其他平台源码、翻译、预编译依赖及上游文档继续保留。

可选静态检查入口（本轮未执行运行验收）：
    cmd.exe /d /c tools\test_resources.cmd
    cmd.exe /d /c tools\test_lua_utf8.cmd
资源检查固定对照原始4526341提交，不以当前 HEAD 作为英文基准；需要 Git 历史。
唯一额外的布局调整是在“关于”中恢复“汉化：Hakuhiro/白希洛”独立一行，
相应增高对话框并下移确定按钮；资源重生成及编译检查均保留并验证该署名。
绘字测试仅覆盖解码、栅格化和 textutf8 入口，不等于高清 HUD 的完整模拟器验收。

许可
----
源码许可见 COPYING、documentation/License.txt 和各子项目源文件。
发布包的 GPL、SFMT、unRAR 声明位于 documentation/；Lua、7-Zip 和
Fusion Pixel 的附加声明位于 documentation/licenses/。
源码与二进制发布包一起提供，便于获取本次构建对应的源代码。
