# LeadBot Vibe Drafting Design

## Goal

让 `LeadBot` 从“单次规则起草器”升级成“对话式 studio copilot”。

用户不需要先手工配置完整的 `AgentBot` 和 `Workflow`，而是可以直接通过自然语言描述工作室目标、角色分工、流程偏好和修改意见，让 `LeadBot` 持续起草、重排和细化 studio 配置。

## Design

### 1. Model-first drafting with safe fallback

`POST /studio/leadbot/draft` 仍然是统一入口，但内部策略改为：

- 优先走模型起草
- 模型不可用或失败时，自动回退到确定性起草器
- 返回结果里显式标注 `draft_source`

这样既能获得自然语言配置的灵活性，也不会牺牲控制台的稳定性。

### 2. Conversational draft state

`LeadBotDraftRequest` 增加两类上下文：

- `conversation`
- `current_draft`

这使得 LeadBot 不再是“每次重新生成一套草案”，而是可以理解“当前草案是什么、用户刚刚又说了什么、这一轮应该改哪里”。这正是 vibe coding 式 studio configuration 的核心。

### 3. Structured model output

模型不直接返回最终 manifest，而是先返回中间草案结构：

- agent drafts
- workflow draft
- rationale
- suggested next prompts

然后由服务层把这些结果映射成真实的 `AgentBot` / `WorkflowDefinition`。这样可以保持 schema 稳定，也便于将来扩展到更多 provider。

### 4. UI as a studio copilot

控制台里的 `Talk to LeadBot` 面板升级成一个对话式工作台：

- 展示 operator / leadbot 对话线程
- 展示当前 draft 是 model / fallback / deterministic
- 展示下一句建议 prompts
- 继续发送自然语言 refinement

低代码 builder 仍然保留，所以最终形态是：

- 对话决定结构
- builder 精修细节

## Verification

验证重点分三层：

- 确定性起草仍能工作
- 模型起草能带着 `conversation + current_draft` 生效
- 模型失败时会安全回退
