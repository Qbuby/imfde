# OpenFDE 世界动态首页设计 QA

- 日期：2026-09-02
- 源视觉真值：`/Users/ice1/openfde-community/docs/design/homepage-world-2026-09-01.png`
- 源视觉 SHA256：`688ddd42c2de6b9def743360500e0b9dd3be31969d6dbba735f6eb08b3c00d67`
- 最终实现截图：`/Users/ice1/.codex/visualizations/2026/08/31/01a056fc-c948-7601-a557-30aa594c7abe/openfde-strict/implementation-final.jpg`
- 本地实现：`http://127.0.0.1:8850/`
- 路由与状态：`/`，30 天，决策者视角，默认选中 OpenAI Deployment Company
- CSS 视口：1487 × 1058
- 源图像素：1487 × 1058
- 实现截图像素：1487 × 1058
- devicePixelRatio：2；浏览器截图输出已归一为 CSS 视口像素，不需要再次缩放

## 对照证据

- 完整并排对照：`/Users/ice1/.codex/visualizations/2026/08/31/01a056fc-c948-7601-a557-30aa594c7abe/openfde-strict/comparison-final.jpg`
- 首屏与时间轴聚焦对照：`/Users/ice1/.codex/visualizations/2026/08/31/01a056fc-c948-7601-a557-30aa594c7abe/openfde-strict/comparison-top-final2.jpg`
- 洞察、关注实体与来源区聚焦对照：`/Users/ice1/.codex/visualizations/2026/08/31/01a056fc-c948-7601-a557-30aa594c7abe/openfde-strict/comparison-bottom-final2.jpg`
- 移动端截图：`/Users/ice1/.codex/visualizations/2026/08/31/01a056fc-c948-7601-a557-30aa594c7abe/openfde-strict/mobile-390-final.jpg`

## Findings

没有未解决的 P0、P1 或 P2 问题。

- 字体与排版：通过。中英文字体层级、标题尺寸、行高和紧凑信息密度与源图一致；动态来源标题按真实数据截断，未出现重叠。
- 间距与布局：通过。页头、标题区、四条时间带、右侧证据栏、问答栏、三列洞察区和底部边界说明在 1487 × 1058 内与源图对齐。
- 颜色与令牌：通过。海军蓝、青绿色以及四条信号带的蓝/橙/紫语义一致；分隔线和浅色面板层级清晰。
- 图片与图标：通过。可见 UI 图标使用本地图标库资源；OpenAI、Palantir 等已映射的品牌标志使用 Simple Icons 13.21.0 原始 SVG，未使用字母头像或手绘替代物。动态实体没有可信映射时使用统一的官方 building 图标。
- 文案与内容：通过。固定界面文案和结构与源图一致；事件、日期、实体与计数来自当前本地数据，因此不会复制设计稿中的示例事实。
- 响应式：通过。390 × 844 下 `scrollWidth = 390`，无横向溢出；时间轴改为可读的纵向列表。
- 可访问性：通过。核心控件均为语义化按钮/标签，具备 aria 状态和 focus-visible；图标 alt 处理正确，支持 reduced-motion。

## 交互与运行检查

- 7 / 30 / 90 天切换：通过，`aria-pressed` 与数据窗口同步。
- 时间轴节点选择：通过，右侧详情随选择更新。
- 关闭详情：通过，清空当前选择并显示空态。
- 决策者 / 从业者视角：通过，详情解释顺序同步切换。
- 本地提问筛选：通过，搜索 `OpenAI` 返回 2 条有明确日期的来源并打开第一条。
- 关注实体标签：通过，人物标签切换后列表更新。
- 导航与 GitHub / 原始来源链接：通过。
- 浏览器控制台错误：0。
- Python 编译、JavaScript 语法、HTTP 路由与静态资源检查：通过。

## 对照迭代历史

1. Pass 1：发现 `.chain-arrow` 未约束尺寸，形成巨型黑色斜线并把变化列表高度推至约 1895px。固定为 12 × 12px 后消除 P1 布局破坏。
2. Pass 2：发现同日事件标题在公司信号带重叠。改为 7/30 天窗口每个同日组只保留一个可见标题，节点和点击目标全部保留，消除 P2 可读性问题。
3. Mobile pass：发现 `.world-below` 在 390px 视口左右各溢出 12px。移除移动端负边距后 `scrollWidth` 回到 390，消除 P2 响应式问题。
4. Asset pass：将实体字母头像替换为可信品牌 SVG 或统一图标库回退，消除 P2 资产替代问题。
5. Final pass：完整视图与上下聚焦区域重新并排检查，无新的 P0/P1/P2。

## Follow-up Polish

- P3：源图中的信号带有更明显的淡色波形纹理；当前实现保持更克制的纯色带和真实关系线，不影响层级、阅读或交互。
- P3：设计稿是策展样例，当前时间轴信号数量和关注实体不同；这是为保证本地数据库事实和日期口径而保留的预期差异。

final result: passed
