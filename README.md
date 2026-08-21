# DSH macOS Pet

<p align="center"><a href="README_EN.md">English</a> · <b>简体中文</b></p>

<p align="center">
  <b>一只跟着你的 agent 换表情的 macOS 桌宠。<br>
  换成你自己的猫也行。</b>
</p>

<p align="center">
  <img src="docs/media/diy-skin.png" width="820" alt="一张猫的照片变成六个状态的桌宠">
</p>
<p align="center">
  <sub>进去一张照片，出来六个状态：空闲、干活、等你、报错、开心、睡着。<br>
  生图跑的是你自己的工具、烧的是你自己的额度，我这边不往任何地方传东西。</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/macOS-only-000000.svg?logo=apple&logoColor=white" alt="macOS only">
  <a href="https://www.npmjs.com/package/dsh-macos-pet"><img src="https://img.shields.io/npm/v/dsh-macos-pet.svg?color=cb3837&label=npm" alt="npm"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/python-系统自带-3776AB.svg" alt="System Python">
  <img src="https://img.shields.io/badge/依赖-零-2ea44f.svg" alt="No dependencies">
  <a href="https://github.com/topics/dsh-plugin"><img src="https://img.shields.io/badge/topic-dsh--plugin-111111.svg" alt="dsh-plugin"></a>
</p>

<p align="center">
  <img src="docs/media/floats-above.png" width="820" alt="桌宠浮在一个全屏编辑器之上">
</p>
<p align="center">
  <sub>它是一个真的 macOS 窗口，不是塞进 DSH 页面里的挂件。<br>
  盖在我正在用的一切上面，全屏也盖得住，不用我告诉它现在该显示什么。</sub>
</p>

---

## 它解决什么

你让 agent 跑一个长任务，然后切去做别的事。它跑完了吗？挂了吗？还是卡在等你点一下授权？

要知道答案，你得切回去看。切回去本身不费时间，费的是它打断你手上正在做的事 —— 而一轮任务里你会切很多次。而且卡在等你授权是最贵的一种：agent 什么都没干，只是在等，而你不知道。

桌宠就是「不用切回去看」。它浮在所有窗口之上，全屏也盖得住，瞄一眼屏幕角落就知道现在是哪种情况。

## 安装

已经有 DSH 的话，一条命令：

```bash
dsh plugin --profile web add dsh-macos-pet
dsh web
```

装完宠物就浮在桌面上了，DSH 页面本身不会被塞任何东西。

从旧版本升级得带 `@latest`：

```bash
dsh plugin --profile web add dsh-macos-pet@latest
```

不带的话写进去的是 `^0.x` 范围，而 caret 作用在 `0.x` 上会锁住次版本号，`^0.1.0` 永远不接受 `0.2.0`。裸命令会报一句 Already up to date，旧版本原地不动。

不想装 DSH、只想看宠物：克隆下来跑 `./bin/dsh-macos-pet`。

想跟 main 分支而不是发布版：

```bash
dsh plugin --profile web add github:Dkrillex/dsh-macos-pet#main
```

**零依赖。** 装它不用先装别的东西，不用编译，也不需要 ffmpeg。跑的是系统自带的 python。

## 使用

| | |
|---|---|
| **拖** | 按住身体任意处。放哪下次就从哪开始。 |
| **点一下** | 展开会话清单：有哪些 DSH 会话、哪个还活着、各自在干什么。再点一下收起。 |
| **免打扰** | 让它安静，直到你自己关掉。agent 照常干活，宠物不再反应。摸它还是会弹一下。 |
| **右键** | 菜单：免打扰、会话清单、皮肤、宠物出现在哪、项目主页、检查更新、退出。 |
| **停掉** | `./bin/dsh-macos-pet --stop`，或者直接停 `dsh web`。 |

它是后台进程，启动之后就脱离终端了，所以开它的那个窗口可以直接关。

## 状态

<p align="center">
  <img src="docs/media/states.png" width="720" alt="空闲、干活、等你、报错、开心、睡着">
</p>

跟着本地 DSH 自动变，没有需要配的东西。

```mermaid
stateDiagram-v2
    [*] --> 空闲
    空闲 --> 干活: DSH 开始跑
    干活 --> 等你: 卡在确认或授权
    等你 --> 干活: 你回应了
    干活 --> 报错: 这一轮失败
    干活 --> 开心: 这一轮跑完
    开心 --> 空闲: 3.2 秒后自己回落
    报错 --> 干活: 下一轮开始
    空闲 --> 打盹: agent 与鼠标同时安静 90 秒
    打盹 --> 空闲: 任何动静，或者戳它一下
```

| 状态 | 什么时候 |
| --- | --- |
| **空闲** | 没事干，会呼吸、偶尔眨眼 |
| **干活** | DSH 正在跑 |
| **等你** | 卡在确认、授权、要你输入 |
| **报错** | 跑挂了 |
| **开心** | 刚跑完一轮，3.2 秒后自己回到空闲 |
| **睡着** | agent 闲着**且**你的鼠标也不动了才打盹，一有动静或者你戳它就醒 |


## 皮肤

<p align="center">
  <img src="docs/media/skins.png" width="600" alt="内置皮肤">
</p>

在右键菜单的皮肤子菜单里挑，或者用 `--skin <id>` 指定启动时用哪套。每套六个状态齐全，每个状态三帧。

| 皮肤 | 动起来 |
|---|---|
| **深索鲸（默认）** | <img src="docs/media/loop-deepseek.gif" width="120" alt="deepseek"> |
| **蓝鲸** | <img src="docs/media/loop-bluewhale.gif" width="120" alt="bluewhale"> |
| **线核** | <img src="docs/media/loop-threadcore.gif" width="120" alt="threadcore"> |
| **鹦鹉螺** | <img src="docs/media/loop-nautilus.gif" width="120" alt="nautilus"> |
| **水母** | <img src="docs/media/loop-jellyfish.gif" width="120" alt="jellyfish"> |
| **Claude** | <img src="docs/media/loop-claude.gif" width="120" alt="claude"> |

> 空闲是 2.4 秒静止，然后一次很短的眨眼。三帧均分我试过，效果不好。

### 每套皮肤的六个状态

顺序：空闲 · 干活 · 等你 · 报错 · 开心 · 睡着

<p align="center">
  <img src="docs/media/skin-deepseek.png" width="820" alt="deepseek">
</p>
<p align="center"><sub>深索鲸（默认）</sub></p>

<p align="center">
  <img src="docs/media/skin-bluewhale.png" width="820" alt="bluewhale">
</p>
<p align="center"><sub>蓝鲸</sub></p>

<p align="center">
  <img src="docs/media/skin-threadcore.png" width="820" alt="threadcore">
</p>
<p align="center"><sub>线核</sub></p>

<p align="center">
  <img src="docs/media/skin-nautilus.png" width="820" alt="nautilus">
</p>
<p align="center"><sub>鹦鹉螺</sub></p>

<p align="center">
  <img src="docs/media/skin-jellyfish.png" width="820" alt="jellyfish">
</p>
<p align="center"><sub>水母</sub></p>

<p align="center">
  <img src="docs/media/skin-claude.png" width="820" alt="claude">
</p>
<p align="center"><sub>Claude</sub></p>

### 用一张图做你自己的皮肤

把一张图交给你的 agent，让它做一套桌宠皮肤。插件里带了个 skill，负责把这张图扩写成一套皮肤要的十八个姿势，六个状态每个三帧。生图是你自己的工具在跑，烧的是你自己的额度，我这边不往任何地方发东西。做好的皮肤落在 `~/.dsh-macos-pet/skins/`，在安装包外面，所以升级插件不会把它删掉。

十八张图烧的是真金白银，所以 skill 中途会停两次让你确认：第一张画出来先看角色对不对，第二张画出来再确认还是同一个角色。半路失败会告诉你缺哪几个，已经生出来的那些留着。

做好之后可以拿出来给人看。一条命令把六个状态拼成一张图：

```bash
./bin/dsh-macos-pet --skin-sheet <你的皮肤id>
```

欢迎投进 [皮肤画廊](SKINS.md)，只交那一张预览图，帧素材留你自己机器上。

## 参数

```bash
./bin/dsh-macos-pet --scale 0.5      # 更小（默认 0.7）
./bin/dsh-macos-pet --skin jellyfish # 指定启动时的皮肤
./bin/dsh-macos-pet --reset          # 忘掉存下来的位置、大小、皮肤
./bin/dsh-macos-pet --stop           # 停掉正在跑的那只
./bin/dsh-macos-pet --foreground     # 前台跑，日志打到当前终端
./bin/dsh-macos-pet --probe          # 自检，不开窗
./bin/dsh-macos-pet --inventory      # 每套皮肤每个状态有几帧
```

## 已知限制

- 宠物四周有一圈透明边距，点在那上面不会穿透到后面的窗口。
- 这一版没有设置窗口，也没有贴边的 mini 模式。
- 生成皮肤的时候这边不显示进度，那十八张图期间你只能看自己 agent 的输出。
- 只支持 macOS。Windows 和 Linux 我没有机器测，短期也不打算做。

它内部怎么跑的、以及我当时选错过哪几个地方，写在 [docs/INTERNALS.zh-CN.md](docs/INTERNALS.zh-CN.md)。

后面想做什么、什么不打算做，写在 [docs/ROADMAP.md](docs/ROADMAP.md)。

## 许可

MIT。

维护：Jackie（[@Dkrillex](https://github.com/Dkrillex)）。

基于 [anneheartrecord/dsh-desk-pet](https://github.com/anneheartrecord/dsh-desk-pet)，同为 MIT 许可；原始版权声明保留在 [LICENSE](LICENSE) 中。
