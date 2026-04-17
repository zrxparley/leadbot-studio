# LeadBot Studio

`LeadBot Studio` 是一个基于 OpenClaw 思路构建的多智能体工作室框架。

它的核心目标不是替代 OpenClaw Gateway，而是提供一个更高层的控制平面，让你可以围绕一个 `LeadBot` 去统一组织、配置、编排、治理多个 `AgentBot`，并把这些定义导出成 OpenClaw 友好的配置起点。

## 这个项目解决什么问题

当你要做一个真正可运营的多智能体工作室时，光有多个 agent 还不够。你通常还需要：

- 一个可以代表工作室对外工作的 `LeadBot`
- 多个职责清晰、可自定义的 `AgentBot`
- workflow/flow 管理能力
- AgentBot 的技能、备注、头像、能力、workspace、工具策略管理
- OpenClaw 配置导出能力
- 统一的治理能力：审批、handoff、A2A allowlist、审计要求

这就是 `LeadBot Studio` 的定位。

## 核心概念

### 1. LeadBot

LeadBot 是控制平面，不是网关替代品。

它负责：

- 任务分解
- workflow 选择
- specialist agent 调度
- 审批与升级
- handoff 协议
- 输出把关

### 2. AgentBot

每个 AgentBot 都可以独立定义：

- `id`
- `role`
- `objective`
- `avatar`
- `remark`
- `workspace`
- `skills`
- `tool_policy`
- `bindings`
- `notes`

### 3. Workflow

每个 workflow 都支持：

- 指定 `LeadBot`
- 指定参与的 `AgentBot`
- 配置 step 顺序
- 配置 step owner
- 配置依赖关系
- 配置 deliverables
- 配置 handoff 目标
- 配置审批点

## 当前已经实现的能力

- FastAPI 控制平面
- `StudioManifest` 配置模型
- `LeadBot` / `AgentBot` / `Workflow` 领域模型
- workflow plan 编译器
- workflow dry-run、运行记录持久化、状态流转
- operator console，可直接发起 run 并推进 run / step 状态
- 低代码 builder console，可通过 Web UI 创建、编辑、删除 AgentBot / Workflow
- Workflow Builder 可视化依赖编排，支持 step graph、依赖预览、拖拽排序
- AgentBot Builder 模板系统，内置 Researcher / Developer / QA / Publisher 骨架
- LeadBot 对话起草，可根据自然语言 brief 自动生成并接好 AgentBot / Workflow 草案
- LeadBot 模型起草引擎，支持“模型优先，规则回退”
- LeadBot 对话 refinement，可带着当前 draft 和对话历史继续用自然语言微调
- LeadBot manifest impact diff，可预览新增 / 更新 / 删除哪些 AgentBot 与 Workflow
- LeadBot workflow review，可预览 step 顺序、依赖、owner、approval gate 的具体变化
- LeadBot execute 模式，可直接通过自然语言 `Send & Apply` 同步工作室
- OpenClaw 配置导出器
- 自动生成默认 studio manifest
- 一个可直接 fork 的默认工作室模板

## 主要接口

- `GET /health`
- `GET /studio/manifest`
- `PUT /studio/manifest`
- `GET /studio/summary`
- `POST /studio/leadbot/draft`
- `POST /studio/leadbot/execute`
- `POST /studio/leadbot/apply-draft`
- `GET /studio/agents`
- `GET /studio/workflows`
- `GET /studio/workflows/{workflow_id}/plan`
- `POST /studio/workflows/{workflow_id}/dry-run`
- `POST /studio/workflows/{workflow_id}/runs`
- `GET /studio/runs`
- `GET /studio/runs/{run_id}`
- `GET /studio/runs/{run_id}/events`
- `PATCH /studio/runs/{run_id}`
- `PATCH /studio/runs/{run_id}/steps/{step_id}`
- `GET /studio/openclaw/export`

## 项目结构

```text
app/
  api/
  core/
  db/
  studio/
docs/plans/
tests/
```

## 本地启动

1. 创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

2. 准备环境变量

```bash
cp .env.example .env
```

如果要启用模型驱动的 LeadBot draft，在 `.env` 中配置：

```bash
LEADBOT_DRAFT_PROVIDER=auto
LEADBOT_DRAFT_MODEL=gpt-5.4
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=
```

不配置时，LeadBot 仍然可以工作，只是会退回内置的确定性起草器。

3. 启动服务

```bash
uvicorn app.main:app --reload
```

4. 打开默认文档

```text
http://127.0.0.1:8000/docs
```

控制台首页：

```text
http://127.0.0.1:8000/studio/console
```

首次访问 `/studio/*` 接口时，系统会自动生成默认 manifest：

```text
app/data/leadbot_studio_manifest.json
```

## 默认工作室模板

项目内置了一套默认的工作室配置：

- `studio-lead`
- `researcher`
- `builder`
- `qa`
- `publisher`

默认附带两个 workflow：

- `build-delivery`
- `research-briefing`

你可以直接修改 manifest，把 bot 的名字、头像、技能、工作流、交付方式替换成你自己的工作室配置。

现在也可以直接在 `/studio/console` 里和 LeadBot 对话，例如：

- `我想做一个产品发布工作室，LeadBot 统筹，研究员负责素材，发布 Agent 负责多渠道分发。`
- `把 QA 改成只在最终交付前介入。`
- `再加一个运营 Agent，专门做上线后的复盘和数据回收。`

控制台现在支持两种节奏：

- `Send to LeadBot`：先起草，再看 impact diff，然后决定是否应用
- `Send & Apply`：直接把这句自然语言变成 studio 变更并同步到 manifest

## OpenClaw 对接思路

这个项目遵循一个原则：

- OpenClaw 负责 agent 隔离、bindings、channel routing、runtime
- LeadBot Studio 负责 orchestration、workflow management、governance、export

也就是说，`LeadBot Studio` 更像是 OpenClaw 之上的“工作室操作系统”。

## 设计文档

详细设计在：

```text
docs/plans/2026-04-16-leadbot-studio-design.md
```

本轮关于模型起草和自然语言 vibe drafting 的设计补充在：

```text
docs/plans/2026-04-17-leadbot-vibe-drafting-design.md
```

整体 roadmap 在：

```text
docs/plans/2026-04-16-leadbot-studio-roadmap.md
```
