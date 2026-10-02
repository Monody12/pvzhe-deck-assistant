# 杂交版卡组助手

植物大战僵尸**杂交版 v3.12** 的外部卡组工具。它把一个小工具栏贴在选卡界面上，用来保存、命名、应用、清空和排序卡组。

- 不修改游戏 EXE、DLL、PAK 或存档，不会触发启动器的 MD5 校验
- 只在普通选卡界面显示；战斗、选关地图或游戏最小化时自动隐藏，避免挡住操作
- Windows 单体可执行文件，无需安装 Python

> 这是非官方粉丝工具，与 PopCap、EA 或杂交版作者无关。请自行拥有合法游戏副本。本仓库不包含任何游戏本体文件。

## 下载

到 [Releases](https://github.com/Monody12/pvzhe-deck-assistant/releases) 下载 `PvZHE-Deck-Assistant.exe`（可改名为 `杂交版卡组助手.exe`）。

1. 启动杂交版 v3.12
2. 运行助手（若游戏以管理员运行，助手也要用管理员运行）
3. 进入普通选卡界面，工具栏会出现在顶部卡槽下方右侧

也可以把 `启动卡组助手.bat` 和 exe 一起放到游戏目录：未开游戏时会尝试启动 `pvzHE-Launcher.exe`。

## 功能

| 操作 | 说明 |
| --- | --- |
| 8 个卡组位 | 可命名，最多 12 个字；双击卡组位改名 |
| 保存 | 把当前选卡写入选中卡组 |
| 应用 | 把选中卡组写回游戏选卡栏 |
| 清空 | 移走已选卡片；默认保留戴夫/关卡锁定卡 |
| 覆盖锁定卡 | 勾选并确认后，应用/清空才会动锁定卡 |
| 排序 | 打开名称条，拖动调整未锁定卡片的顺序 |

卡组保存在当前 Windows 用户目录：

```text
%APPDATA%\PvZHybridDeckAssistant\decks.json
```

## 限制

- 仅验证杂交版 v3.12 的 32 位结构
- 只支持普通选卡，不支持传送带、保龄球等固定卡牌模式
- 槽位不够时先保留锁定卡，再按预设顺序填入其余卡片
- 游戏更新导致内存结构变化时，助手会拒绝写入

## 从源码运行

需要 64 位 Windows 和 Python 3.11+（标准库即可）：

```powershell
python pvz_deck_assistant.py
python pvz_deck_assistant.py --status
python pvz_deck_assistant.py --classic
```

打包单体 exe：

```powershell
powershell -ExecutionPolicy Bypass -File .\build-assistant.ps1
```

## 安全说明

助手会读写本机 `PlantsVsZombies.exe` 的选卡内存，用于改卡组。它不会访问网络，卡组只存在你的用户目录。不要对其他进程使用，也不要把来历不明的 `decks.json` 直接拷进配置目录。
