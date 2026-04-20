# Config Plane Design

## Goal

把 LeadBot Studio 从"运行控制台"升级成"真正可运营的工作室后台"。

Codex 阶段完成了 LeadBot 的 vibe drafting 和 proposal review 流程。
本阶段（config plane）的目标是：让 AgentBot 和 Workflow 的创建与编辑也全部在 Web UI 内完成，
并把 Chat 页面升级成真正的 Vibe Coding 双栏工作台。

## What Changed in This Sprint

### 1. Agents Config Page (`/studio/agents-config`)

新增了独立的 Agent 配置页。页面包含：

- LeadBot 全貌卡片（含 coordination style、manages 数量、workflow 关联）
- Specialist Agent 富文本卡片列表（头像、技能标签、bindings 数量、capabilities）
- 直接从列表 Edit / Delete Agent（Delete 带确认弹窗）
- New AgentBot 按钮 → 打开原有 builder drawer（含模板系统 + 完整字段）
- OpenClaw export 预览面板（agents / bindings / A2A allowlist）
- 汇总指标：总 agent 数、specialist 数、总技能数、总 bindings 数

### 2. Chat Page Vibe Coding Dual-Panel (`/studio/chat`)

把原来嵌在 Console 里的 LeadBot chat 模块升级为独立双栏页面：

**左栏 — Chat with LeadBot**
- 完整的多轮对话线程（operator / leadbot 气泡）
- textarea 输入框 + `Send to LeadBot` / `Send & Apply` 两个行动
- `Cmd+Enter` 快捷键发送
- Vibe Prompts 建议卡：LeadBot 每轮自动返回 suggested_next_prompts，点击填入输入框
- Draft Mode chip 显示当前是 model / fallback / deterministic draft
- Reset Thread 清空对话状态

**右栏 — Proposal Review**
- Proposal 元数据卡（id、status、brief、draft source、rationale）
- Workflow Preview：实时 Mermaid 可视化，每次 draft 后自动更新
- Manifest Impact diff：creates / updates / removals 列表，含 workflow step review
- Approval Actions：Approve & Apply / Request Revision / Reject（带 note 输入）
- Proposal History 列表：本 session 内所有 proposals，可切换查看，pending 状态可快速审批

### 3. Navigation

导航栏新增 `Agents` 入口，路由到 `/studio/agents-config`。
Chat 页完全使用新双栏布局，不再复用 Console 中心面板。

## Architecture Notes

```
/studio/console      → 综合控制台（所有功能聚合）
/studio/chat         → Vibe Coding 双栏工作台（独立入口）
/studio/agents-config → Agent 配置管理页（独立入口）
/studio/workflows    → Workflow 配置 + Run 控制（已有）
/studio/proposals    → Change Proposal 审批列表（已有）
```

所有页面共用同一个 `console.html`，通过 `data-page-block` 属性和 `applyPageMode()` 函数控制哪些 section 可见。

新增的 `chat-standalone` data-page-block 只在 `/studio/chat` 路由下显示。
新增的 `agents-config` data-page-block 只在 `/studio/agents-config` 路由下显示。

## Design Principles

- **Configuration-first**: 所有配置操作都在 UI 内完成，不需要手动编辑 JSON manifest
- **Vibe Coding loop**: 自然语言 → Proposal → Review → Approve/Reject，每一轮都是原子的
- **Proposal as audit trail**: 每次自然语言变更都产生 proposal 记录，完整可溯源
- **Builder drawer stays central**: 精细字段编辑仍走 editor drawer，UI 不过度碎片化

## Next Sprint Candidates

1. **Model integration**: 接入真实 LLM，让 LeadBot draft 走 model-backed 路径
2. **Workflow visual editor**: Workflows 页内直接拖拽编辑 step 顺序和依赖
3. **Agent avatar upload**: 支持上传头像图片，不只是 URL
4. **Proposal notification**: Proposal pending 状态时 UI 顶部 badge 提示
5. **OpenClaw runtime bridge**: 把 workflow run 真正分发到 OpenClaw agent runtime
