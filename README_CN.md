# Planner Probe v1：四个 agent 系统的小型观察实验

建议首先阅读本文件。这个包已经包含待修复项目、公开测试、样例日志、独立验收工具、参考实现和观察表。你不需要另找数据或编写实验代码。

这是一个**人为设计、贴近实际科研工作的项目**：修复和扩展 Python 实验日志统计工具。目标是观察 Claude Code、Codex、DeepSeek Harness、Qoder 怎样拆任务、选择行动、利用反馈和决定结束。它们是 agent 系统，底层模型需要另外记录。

## 任务与规模

给 agent 的任务是修复不正确的 token 统计，增加按模型和 benchmark 分组、CSV 导出，保持原 CLI 可用，并补充测试。完整需求在 `starter/TASK.md`，规定了重复记录、缓存 token、未完成任务、损坏日志和零分母的处理口径。

初始项目只有 5 个核心 Python 文件（约 166 行），3 份 JSONL 文件（30 个不同任务、4 条重复记录、2 条无效记录），以及 9 个公开单元测试。初始测试 **6 通过、3 失败** 是实验设计，不是安装失败。分组和 CSV 功能尚未实现。

它提供四类观察机会：跨文件理解和拆分工作；搜索/阅读/写脚本/测试等行动选择；测试或命令输出驱动修正；用实际结果和验收标准判断完成。简单任务不保证触发子 agent、压缩或每一种现代规划能力，未触发就如实记录。

## 包内内容

| 路径 | 给谁使用 |
|---|---|
| `starter/` | agent 唯一可见的项目模板 |
| `tools/prepare_run.py` | 研究者创建互相独立的初始副本和 Git 基线 |
| `tools/evaluate.py` | 研究者运行独立验收；验收数据生成在 workspace 外 |
| `tools/snapshot.py` | 保存阶段结束时的完整代码，包括新文件 |
| `researcher/reference.py` | 验收器校准用的正确实现；**不要给 agent 看** |
| `researcher/FOLLOWUP.md` | 可选第二阶段的统一新需求 |
| `researcher/observations.csv` | 按事件记录四类行为 |
| `researcher/comparison.csv` | 跨系统结果汇总模板 |
| `docs/OBSERVATION_GUIDE_CN.md` | 怎样区分事实、推断、完成声明和真实验收 |
| `VALIDATION.md` | 本包自身的实际校准结果；不是四个系统的实验成绩 |

## 1. 解压和准备

在 macOS / Linux 上使用 Python 3.10+ 和 Git。任务项目及验收器都只用 Python 标准库，无须 pip 安装。四个产品的账号、模型权限和客户端需要你自行准备。

```bash
unzip planner_probe_v1.zip
cd planner_probe_v1
python3 --version
git --version
```

在这个目录运行以下四条命令。它们会把纯任务副本放到你的主目录下；**不要让 agent 打开整个实验包**。

```bash
python3 tools/prepare_run.py --system claude --trial 1
python3 tools/prepare_run.py --system codex --trial 1
python3 tools/prepare_run.py --system deepseek --trial 1
python3 tools/prepare_run.py --system qoder --trial 1
```

默认路径分别为：

```text
~/planner_probe_runs/claude/natural_01/workspace
~/planner_probe_runs/codex/natural_01/workspace
~/planner_probe_runs/deepseek/natural_01/workspace
~/planner_probe_runs/qoder/natural_01/workspace
```

各自的 `../records/` 保存元数据、日志和观察表。脚本拒绝覆盖已有目录；重跑使用 `--trial 2`，不要沿用上一次已经修好的代码。可用 `--runs-root /your/path` 改存储位置。

可选先查看初始项目状态（这不是被测 agent 的运行）：

```bash
cd starter
python3 -m agentstats fixtures
python3 -m unittest discover -s tests -v
cd ..
```

测试出现 3 个已知失败属正常。不要先修复 starter；agent 每次都从这个相同初始状态开始。

## 2. 使用完全相同的起始指令

四个系统都使用新会话、普通执行模式，并输入同一句话：

```text
Complete the task in TASK.md.
```

`TASK.md` 已在每个 workspace 内。这条指令不规定执行顺序、不强制显式规划，也不要求逐步解释内部推理。不要同时给某一个系统额外提示 bug 位置。若出现必须澄清的问题，依据 TASK.md 回答并保存原文；记录为人工干预。

在 `records/metadata.json` 中补上客户端版本、实际后端模型、推理强度、工具/扩展、权限及额外用户或项目指令。保留相同的时间预算（默认 30 分钟，研究者手动计时；包内不会自动杀掉 agent）。到时尚未完成就记录预算终止。可以先做一个不计分 pilot，再统一调整四个系统的预算。

## 3. Claude Code

已经安装并登录时，在新终端中运行：

```bash
cd ~/planner_probe_runs/claude/natural_01/workspace
claude --version
claude
```

输入统一起始指令。允许当前项目内所需的读写与 Python 执行，保持普通模式。`Ctrl+O` 查看详细会话/工具操作，`Ctrl+T` 查看任务列表（版本支持时）。结束后在会话内输入：

```text
/export ../records/claude-A.txt
```

保存关键工具输出的截图，尤其是被折叠或截断的失败和重测结果。导出纯文本不代表拿到了全部原始事件或隐藏推理。

尚未安装时参阅 [Claude Quickstart](https://code.claude.com/docs/en/quickstart)；记录方式见 [Interactive mode](https://code.claude.com/docs/en/interactive-mode) 和 [Commands](https://code.claude.com/docs/en/commands)。

## 4. Codex

先通过 `codex` 完成登录。然后在该副本目录运行：

```bash
cd ~/planner_probe_runs/codex/natural_01/workspace
codex --version
codex exec --sandbox workspace-write --json "Complete the task in TASK.md." > ../records/codex-A.jsonl 2> ../records/codex-A.stderr.log
```

该命令把事件和运行消息写入文件，终端可能暂时没有输出。`prepare_run.py` 已建立 Git 仓库。`workspace-write` 允许改动工作区，无须关闭整个 sandbox。若环境限制阻止正常执行，记录具体错误和干预，不要把环境问题当作规划失败。

在 JSONL 中观察计划更新、命令执行、文件修改、结果、结束事件和 usage。一次命令调用内部可能执行多个操作，不能把事件行数直接当工具次数。官方：[非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode)、[CLI](https://learn.chatgpt.com/docs/codex/cli)。

也可以使用交互式 `codex` 输入同一句话，但应记录接口条件；不要把交互与非交互的差别自动归因于模型。

## 5. DeepSeek Harness

需要 Node.js/npm，以及可用的模型凭据。在对应副本目录执行：

```bash
cd ~/planner_probe_runs/deepseek/natural_01/workspace
npx @deepseek-ai/dsh web
```

终端保持运行，然后：

1. 打开启动日志打印的本地地址/认证链接（通常端口 3080，以实际输出为准）。
2. 首次使用在 **Settings → Models** 配置自己的模型与 API key。记录实际模型、Harness 版本和 preset。
3. 在 **Choose workspace** 添加并选中 `~/planner_probe_runs/deepseek/natural_01/workspace` 对应的绝对路径。**只在终端 cd 进去并不代表 Web 界面已经选中这个工作区。**
4. 新建会话，输入统一起始指令。
5. 完成后在聊天中输入 `/export`，或选择 **Download session log**。浏览器会下载 ZIP，把它放入这次运行的 records 目录。

`/export` 不接受文件名参数；导出包括会话事件及子会话/附件。检查导出的 `session.jsonl` 或带版本号的会话文件。不要将 API key 放进任务文件或实验报告。

官方：[Quickstart](https://deepseek-harness.github.io/deepseek-harness/en/guide/quickstart)、[源码](https://github.com/deepseek-ai/deepseek-harness)、[会话导出](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/session-query/session-log-export/README.md)。

`npx` 可能安装当前版本；第一次记录实际版本，后续重复实验固定同一版本，不要默默升级。需要固定版本时用 `npx @deepseek-ai/dsh@你记录的版本 web`。

## 6. Qoder

按当前官方文档，启动命令是 `qoder`，虽然 npm 包名仍可能是 `@qoder-ai/qodercli`。安装后：

```bash
cd ~/planner_probe_runs/qoder/natural_01/workspace
qoder
```

先登录并选定可用模型，使用普通 Agent 流程，输入统一起始指令。用 `/status` 记录版本和模型。结束后：

```text
/export ../records/qoder-A.txt
/usage
```

记录公开的用量字段；credits 不等于 tokens，未提供就写 N/A。若只使用 IDE，打开这一份 workspace 文件夹，在普通 Agent 聊天里输入统一指令，保存会话历史、工具详情和关键截图；不要在主条件里单独启用 Quest/Spec/Plan。

官方：[Installation](https://docs.qoder.com/cli/installation)、[Quickstart](https://docs.qoder.com/cli/quickstart)、[Commands](https://docs.qoder.com/cli/commands)。界面或旧版本命令不同，以安装版本的帮助为准并记录。

## 7. 每个系统结束后独立验收

先保存该系统的结束声明与会话日志。然后开一个**研究者终端**，回到解压后的 `planner_probe_v1` 根目录。以 Claude 为例：

```bash
python3 tools/evaluate.py --workspace "$HOME/planner_probe_runs/claude/natural_01/workspace" --stage A --output "$HOME/planner_probe_runs/claude/natural_01/records/grade-A.json"
python3 tools/snapshot.py --workspace "$HOME/planner_probe_runs/claude/natural_01/workspace" --output "$HOME/planner_probe_runs/claude/natural_01/records/code-A.zip"
```

测其他系统，把路径中的 `claude` 替换为 `codex`、`deepseek`、`qoder`。独立验收不依赖 agent 自己修改的测试。即使 agent 说“所有测试都通过”，也以验收结果另行登记。

验收输出的 `acceptance_passed` 表示该阶段是否整体通过。部分检查通过的比例只用于分析错误，不是任务成功率。README/测试新增质量仍需人工检查；自动验收不能证明所有未测试输入都正确，也不是对恶意修改防篡改的评测。

**不要把详细验收失败信息发回 agent 后，覆盖第一次成绩。** 若想研究修复反馈，可以另记一个 assisted/repair 条件，但不与首轮混合。

## 8. 可选 Stage B：观察收到新需求后的调整

先完成 Stage A 验收与代码快照，再在**同一个会话**发送 `researcher/FOLLOWUP.md` 的内容。这个后续需求是增加 `--strict`：无效记录存在时仍正常产出报告，但最终退出码为 2；其他行为保持。

Claude/Qoder/DSH 直接继续原会话。Codex 如果使用非交互模式，需要恢复该次 JSONL 的 `thread.started` 中记录的会话，而不是启动全新的实验副本；可以在交互式 Codex 中恢复对应会话后粘贴需求。恢复方式以所装版本的会话帮助为准。

继续保存 B 阶段日志，然后运行同样的验收命令，把 `--stage A` 改成 `--stage B`，把输出文件改成 `grade-B.json` 和 `code-B.zip`。Stage B 验收还会检查 Stage A 的原有能力。A 未通过时，B 可以用于观察，但不能解释成从正确基线做扩展。

这是“需求变化后的调整”，不等同于“收到执行错误后的恢复”。后者看日志里真实的失败 → 后续行动 → 重测链条。

## 9. 这周要得到什么

先各跑一次 Stage A：四份完整执行记录、四份最终代码、四份独立验收结果、一张对照表。选每个系统 1—2 个有证据的行动选择进行解释。如果有时间，再运行 Stage B 或从初始版本各重复三次。

用 `records/observations.csv` 按事件记：计划、动作、反馈、完成；用 `researcher/comparison.csv` 汇总。详细示例和归因边界见 `docs/OBSERVATION_GUIDE_CN.md`。

你当前研究的 token 优化可以从一个观察到的子问题开始，比如核算几条日志的小计、搜索定位代码、选择重测范围。这个项目涉及修改文件，整个任务无法全程 internal reasoning。以后比较 internal / external / hybrid 时，应固定同一模型和框架，并统计选择器本身及后续重试的总成本。

**注意两种 token 不同：**样例文件里的 token 是待统计数据；四个系统为完成此任务消耗的 token 才是你的效率指标。后者从实际 usage 取值，不要用前者代替。

## 可复现与限制

本包验证了任务初始状态、独立验收器和正确实现，不代表已经运行这四个产品。产品账号、配额和用户环境需要实际使用时确认。官方操作说明核对日期：2026-09-15。

一次案例用于解释机制，不能证明哪个系统总体更强或你的方法能保证成功率不下降。不同产品后端模型、提示词、工具、上下文、计费口径均可能不同。缺失日志或 usage 标记未观察到/未提供，不补造数值。

研究者文件与 workspace 分开能降低意外泄露，但同一用户权限下不是安全隔离。正式盲测需单独环境只挂载 workspace。本任务是研究样例，不是经过外部验证的标准 benchmark。
