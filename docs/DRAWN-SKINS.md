# 画一套皮肤（不用生图工具）

一套皮肤是十八张图：六个状态，每个状态三帧。默认的做法是交给图像模型 —— README 里那条路径用你自己的画图工具和额度，把一张照片扩写成十八个姿势。

这里是另一条路：**用几何画出来。** 不需要生图工具，不需要 API 额度，不需要联网，同一份输入在任何机器上产出同样的字节。代价是风格 —— 出来的是干净的扁平矢量感，不是插画。

内置的 **Claude** 和 **星星** 两套都是这么来的。

---

## 三步

一套皮肤在 [scripts/draw_skin.py](../scripts/draw_skin.py) 里就是一个 `Spec`：五个颜色，加二十来个比例。姿势是共享的，不用你写。

**一、加一个 Spec。** 复制 `SPECS` 里现有的一条，改名字、改颜色：

```python
"mycat": Spec(
    palette=Palette(
        body=(120, 160, 210),        # 主体
        body_dark=(88, 124, 170),    # 描边、手臂
        body_light=(160, 196, 238),  # 交替的星芒
        face=(246, 244, 238),        # 脸盘
        ink=(48, 44, 56),            # 眼、嘴
    ),
),
```

只给调色板就能跑 —— 比例有一整套默认值。想调轮廓再写 `shape=Shape(...)`，只覆盖你要改的那几项。

**二、画。**

```sh
./scripts/draw_skin.py --list            # 看有哪些 Spec
./scripts/draw_skin.py --skin mycat      # 写进 assets/source/mycat/
```

**三、走和其他皮肤同一条构建管线。**

```sh
./scripts/build_frames.py --skin mycat
```

这一步做抠像、统一尺寸、把基线对齐到和其他皮肤一致的位置，然后写出两棵树和 `assets/skins/manifest.json` 里的条目。

想让它出现在右键菜单里，再往 [src/dsh_macos_pet/skins.py](../src/dsh_macos_pet/skins.py) 的 `BUILTIN_SKINS` 加一行。

---

## 能调什么

**调色板**，五个颜色，就是上面那五个。

**比例**，`Shape` 里的字段，全部以输出像素为单位：

| | |
|---|---|
| `body_cy` `body_rx` `body_ry` `rim` | 身体椭圆和描边宽度 |
| `face_dy` `face_rx` `face_ry` | 脸盘的位置和大小 |
| `eye_dx` `eye_dy` `eye_r` `brow_dy` `mouth_dy` | 五官，**相对脸中心** |
| `crest_rays` `crest_reach` `crest_inner` `crest_w0` `crest_w1` | 星芒的根数、长度、根部半径、粗细 |
| `crest_alt` | 奇数根星芒相对偶数根的长度。交替（0.78）读起来是鬃毛，等长（1.0）读起来是星星 |
| `crest_down_limit` `crest_floor_margin` | 朝下的星芒怎么处理，见下 |
| `arm_*` `hand_r` | 手臂粗细、肩膀位置、手的大小 |
| `prop_scale` | 头顶那些字形（`?` `!` `z` 星火）往外推多远 |

改比例比改颜色划算得多。换色只是换色；改 `crest_rays` 和 `crest_reach` 会换掉轮廓，而轮廓才是缩到 100 多像素之后还能认出来的东西。

---

## 两条硬约束

这两条不是风格建议，是 [scripts/check_frames.py](../scripts/check_frames.py) 会判失败的东西。代码已经替你守住了，但你改比例的时候可能撞上。

**一、十八帧的最低点必须一样。** 门槛会量每帧包围盒的底边，同一套皮肤里状态之间差超过 20px 就判失败 —— 因为宠物一开始干活就往下掉一截，看起来像 bug。

所以身体永远是画面里最低的东西，而且身体从不移动：

- 朝下超过 `crest_down_limit` 的星芒直接不画（原来是裁短，会在身体下面留一排小疙瘩）
- 低角度的侧向星芒裁短到 `crest_floor_margin` 之内
- 手臂被钳制在腹线以上
- 所有自由字形放在头顶

**你改比例时要注意的**：如果把 `body_ry` 改小而 `crest_reach` 改大，会有更多星芒被裁短。这不会破坏基线（钳制逻辑保证了），但会影响观感 —— 画完看一眼。

**二、角色身上不能有接近底色的颜色。** 品红底 `#FF00FF` 是抠像用的。任何不透明像素与它的通道差之和小于 60，门槛就报「背景被填回来了」。

这一条 `Palette.check()` 在开画之前就替你拦了，所以你会立刻收到一句明确的报错，而不是等构建完、门槛解码帧之后才发现。想知道余量有多大：Claude 那套最近的一个颜色（奶白）距离是 278。

---

## 怎么检查自己画的东西

```sh
# 六个状态拼成一张，就是 README 里那种图
./bin/dsh-macos-pet --skin-sheet mycat

# 全部帧拼在深色底上 —— 深色是故意的：
# 在品红底上看不出抠像残留，在炭灰底上一眼就能看到
./scripts/contact_sheet.py

# 逐像素跑门槛：破洞、底色污染、GIF/PNG 轮廓一致性、基线
./scripts/check_frames.py

# 连测试一起（美术门槛默认跳过，这个开关打开它）
DSH_PET_ART_CHECK=1 npm test
```

`check_frames.py` 除了报失败还会报警告。有一条值得单独说：**detached prop mass** 掉得很厉害的时候，它分不清「字形和身体贴到一起了」还是「字形消失了」—— 两种在它眼里一样。星星那套就撞过：问号落在一根星芒上，看起来完全正常，但融进了身体的连通块。把 `prop_scale` 调大就好了。所以看到这条警告，去看图，别直接忽略。

---

## 几个我踩过的坑

- **五官的偏移量是从脸中心量的**，不是身体中心。按身体中心算会让眼、眉、嘴整体偏 4px —— 单看不明显，和别的皮肤并排就出来了。
- **曲线要分段。** 三个点连出来是两条直线，交点是个尖 —— 嘴会变成鸟喙。`Canvas.arc()` 默认分十段。
- **描边画在内侧。** 身体外缘就是基线的锚点，往外加描边会把它推下去。
- **循环内每一帧都要有道具。** 三帧里有一帧没有那个 `?`，看起来就是闪烁。让它变大变小、飘动，但别让它消失。
- **改完 Spec 之后跑一次哈希比对**，确认你没有顺手动到别人的皮肤：

  ```sh
  find assets/source/claude -name '*.png' | sort | xargs shasum -a 256 | shasum -a 256
  ```

  这个数字在重构渲染器前后必须一致。它逮到过一个真 bug。

---
---

# Drawing a skin, with no image tool

A skin is eighteen stills: six states, three frames each. The usual way to get
them is an image model — the path in the README spends your own image tool and
your own credits turning one photo into eighteen poses.

This is the other way: **draw them from geometry.** No image tool, no API
credits, no network, and the same input produces the same bytes on any machine.
The cost is style — you get clean flat vector-ish art, not illustration.

The built-in **Claude** and **Star** skins are both made this way.

---

## Three steps

A skin is a `Spec` in [scripts/draw_skin.py](../scripts/draw_skin.py): five
colours and about twenty proportions. The poses are shared, so you do not write
any of those.

**1. Add a Spec.** Copy one from `SPECS` and change the name and the colours:

```python
"mycat": Spec(
    palette=Palette(
        body=(120, 160, 210),        # main mass
        body_dark=(88, 124, 170),    # rim, arms
        body_light=(160, 196, 238),  # alternating rays
        face=(246, 244, 238),        # face plate
        ink=(48, 44, 56),            # eyes, mouth
    ),
),
```

A palette alone is enough to run — every proportion has a default. Add
`shape=Shape(...)` and override only the fields you want when you are ready to
change the silhouette.

**2. Draw.**

```sh
./scripts/draw_skin.py --list            # what specs exist
./scripts/draw_skin.py --skin mycat      # writes assets/source/mycat/
```

**3. Build it the same way as every other skin.**

```sh
./scripts/build_frames.py --skin mycat
```

That keys the plate out, normalises the size, puts the baseline where every
other skin's is, and writes both trees plus the entry in
`assets/skins/manifest.json`.

To make it selectable in the right-click menu, add a line to `BUILTIN_SKINS` in
[src/dsh_macos_pet/skins.py](../src/dsh_macos_pet/skins.py).

---

## What you can change

**The palette** is the five colours above.

**The proportions** are the fields on `Shape`, all in output pixels:

| | |
|---|---|
| `body_cy` `body_rx` `body_ry` `rim` | body ellipse and rim width |
| `face_dy` `face_rx` `face_ry` | where the face plate sits, and how big |
| `eye_dx` `eye_dy` `eye_r` `brow_dy` `mouth_dy` | features, **relative to the face centre** |
| `crest_rays` `crest_reach` `crest_inner` `crest_w0` `crest_w1` | ray count, length, inner radius, thickness |
| `crest_alt` | odd rays relative to even ones. Alternating (0.78) reads as a mane, equal (1.0) reads as a star |
| `crest_down_limit` `crest_floor_margin` | what happens to downward rays, see below |
| `arm_*` `hand_r` | arm thickness, shoulder position, hand size |
| `prop_scale` | how far out the overhead glyphs (`?` `!` `z`, sparkles) sit |

Proportions buy far more than colours. A recolour is a recolour; changing
`crest_rays` and `crest_reach` changes the silhouette, and the silhouette is
what survives being scaled down past a hundred pixels.

---

## Two hard constraints

These are not style advice — [scripts/check_frames.py](../scripts/check_frames.py)
fails a skin over them. The code already holds both for you, but you can walk
into them by changing proportions.

**1. The lowest pixel is identical in all eighteen frames.** The gate measures
the bottom of each frame's bounding box and fails a skin whose states sit more
than 20px apart, because a pet that drops when it starts working reads as a bug.

So the body is always the lowest thing in frame, and the body never moves:

- rays aimed further down than `crest_down_limit` are dropped, not shortened
  (shortening left a row of stubs under the body)
- low side rays are shortened to stay `crest_floor_margin` clear of the belly
- arms are clamped above the belly line
- every free glyph is placed overhead

**What to watch when you change proportions:** a smaller `body_ry` with a
bigger `crest_reach` means more rays get shortened. That cannot break the
baseline — the clamp guarantees it — but it changes how the thing looks. Draw it
and take a look.

**2. No colour on the character may come near the plate.** The magenta
`#FF00FF` background is what gets keyed out. Any opaque pixel whose
sum-of-channel distance to it is under 60 is reported as background filled back
in.

`Palette.check()` catches this before drawing anything, so you get a clear error
instead of finding out after a build and a decode. For a sense of the margin:
Claude's closest colour to its own plate is the cream face, 278 away.

---

## Checking your work

```sh
# the six states in one strip, the image the README shows
./bin/dsh-macos-pet --skin-sheet mycat

# every frame tiled on a dark plate. Dark on purpose: leftover background is
# invisible against magenta and obvious against charcoal
./scripts/contact_sheet.py

# the gate, per pixel: holes, plate contamination, gif-vs-png silhouettes, baselines
./scripts/check_frames.py

# and with the tests, which skip the art gate unless you ask for it
DSH_PET_ART_CHECK=1 npm test
```

`check_frames.py` reports warnings as well as failures, and one is worth calling
out: when **detached prop mass** collapses, it cannot tell "the glyph fused with
the body" from "the glyph vanished" — they look the same to it. The Star skin hit
exactly this: its question mark landed on a ray, stayed perfectly legible, and
merged into the body's connected component. Raising `prop_scale` fixed it. So
when that warning appears, go and look at the frames rather than dismissing it.

---

## Things that caught me out

- **Feature offsets are measured from the face centre**, not the body centre.
  Computing them against the body puts the eyes, brows and mouth 4px out — not
  obvious alone, obvious next to another skin.
- **Curves need segments.** Three points make two straight lines meeting at a
  point, and a mouth drawn that way is a beak. `Canvas.arc()` uses ten.
- **Rims are drawn inward.** The outer edge of the body is what the baseline is
  anchored to, and thickening it outward moves it.
- **Every frame of a loop needs its prop.** A `?` missing from one of three
  frames is a flicker. Let it grow, shrink and drift; do not let it disappear.
- **Hash your neighbours after editing a Spec**, to prove you did not disturb a
  skin you were not working on:

  ```sh
  find assets/source/claude -name '*.png' | sort | xargs shasum -a 256 | shasum -a 256
  ```

  That number has to survive a refactor of the renderer. It has already caught
  one real bug.
