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
- OpenClaw 配置导出器
- 自动生成默认 studio manifest
- 一个可直接 fork 的默认工作室模板

## 主要接口

- `GET /health`
- `GET /studio/manifest`
- `PUT /studio/manifest`
- `GET /studio/summary`
- `GET /studio/agents`
- `GET /studio/workflows`
- `GET /studio/workflows/{workflow_id}/plan`
- `POST /studio/workflows/{workflow_id}/dry-run`
- `POST /studio/workflows/{workflow_id}/runs`
- `GET /studio/runs`
- `GET /studio/runs/{run_id}`
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

3. 启动服务

```bash
uvicorn app.main:app --reload
```

4. 打开默认文档

```text
http://127.0.0.1:8000/docs
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

整体 roadmap 在：

```text
docs/plans/2026-04-16-leadbot-studio-roadmap.md
```
