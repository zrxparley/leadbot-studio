# Config Plane Sprint v2 — Multica-Inspired Enhancement

## 1. 背景与目标

受 [Multica](https://github.com/multica-ai/multica) 项目启发，LeadBot Studio 需要在 Model Integration、Workflow Visual Editor、Avatar Upload、Proposal Notification、OpenClaw Runtime Bridge 五个方向进行增强。

**Multica 的设计精髓：**
- 看板式 Agent 交互（Kanban-style）
- 实时进度流（WebSocket）
- 代理即队友概念
- 轻量级管理界面
- 本地守护进程模型

## 2. 功能优先级

### P0 — Model Integration（Model Integration）

**目标：** 让 LeadBot draft 走真正的 model-backed 路径

**当前状态：** 已有 `_draft_with_model()` 框架，但 OpenAI API 调用可能失败

**实现方案：**
1. 完善 `.env` 配置指南
2. 添加模型 Provider 切换（OpenAI / Azure / 本地模型）
3. 完善 error handling 和 fallback 逻辑
4. 添加 draft_source 状态显示（model / deterministic / fallback）

**配置示例：**
```bash
# OpenAI
LEADBOT_DRAFT_PROVIDER=openai
LEADBOT_DRAFT_MODEL=gpt-4o
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1

# Azure OpenAI
LEADBOT_DRAFT_PROVIDER=azure
LEADBOT_DRAFT_MODEL=gpt-4o
AZURE_OPENAI_ENDPOINT=https://xxx.openai.azure.com
AZURE_OPENAI_KEY=xxx

# 本地模型（如 LM Studio）
LEADBOT_DRAFT_PROVIDER=openai-compatible
LEADBOT_DRAFT_MODEL=llama3.3-70b
OPENAI_BASE_URL=http://localhost:1234/v1
OPENAI_API_KEY=local
```

### P1 — Workflow Visual Editor

**目标：** Workflows 页内直接拖拽编辑 step 顺序

**设计参考：** Multica 的 Kanban 交互风格

**实现方案：**
1. 添加 step 拖拽排序功能（使用原生 HTML5 Drag & Drop API）
2. 可视化依赖连线
3. 添加 step 快捷操作（删除、上移、下移、插入依赖）
4. 实时预览 workflow graph（Mermaid）

**交互设计：**
- `.step-card` 添加 `draggable="true"`
- 拖拽时高亮目标位置
- 松开时自动更新 `depends_on` 依赖
- 依赖检查：防止循环依赖

### P2 — Agent Avatar Upload

**目标：** 支持上传头像图片，不只是 URL

**实现方案：**
1. 新增 `POST /studio/upload` API（multipart form）
2. 头像存储在 `app/data/avatars/` 目录
3. 返回相对路径 `/studio/avatars/{filename}`
4. Avatar input 改为支持 URL 或本地文件上传
5. 支持预览裁剪

**技术细节：**
```python
# 新增 API endpoint
@router.post("/studio/upload", include_in_schema=False)
async def upload_file(request: Request):
    form = await request.form()
    file = form["file"]
    # 保存到 app/data/avatars/
    # 返回访问 URL
```

### P3 — Proposal Notification

**目标：** Proposal pending 时 UI 顶部 badge 提示

**设计参考：** Multica 的实时通知风格

**实现方案：**
1. Navigation bar 添加 badge（显示 pending 数量）
2. 使用 SSE 或轮询获取 pending proposals
3. 添加声音提示选项（可配置）
4. 移动端下拉菜单显示

**UI 设计：**
```html
<nav>
  <a href="/studio/proposals">
    Proposals
    <span id="proposalBadge" class="badge" hidden>3</span>
  </a>
</nav>

<style>
.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--warning);
  color: white;
  font-size: 0.75rem;
  font-weight: 600;
}
</style>
```

### P4 — OpenClaw Runtime Bridge

**目标：** 把 workflow run 真正分发到 OpenClaw agent runtime

**设计参考：** Multica 的本地守护进程模型

**实现方案：**
1. 新增 `POST /studio/runs/{run_id}/dispatch` API
2. 读取 OpenClaw 配置（默认 `~/.openclaw`）
3. 通过 OpenClaw CLI 或 API 分发任务
4. 接收运行状态回传（WebSocket / SSE）
5. 更新 run 状态

**架构：**
```
LeadBot Studio → OpenClaw CLI → Local Agent Daemon
                                    ↓
                              Agent Execution
                                    ↓
                              Status Callback
                                    ↓
                              LeadBot Studio ← WebSocket
```

**OpenClaw dispatch 格式：**
```json
{
  "workflow_id": "build-delivery",
  "run_id": "run-xxx",
  "input_summary": "用户请求内容",
  "lead_agent_id": "studio-lead",
  "steps": [
    {
      "step_id": "intake",
      "owner_agent_id": "studio-lead",
      "command": "/openclaw exec --agent studio-lead --input intake-brief"
    }
  ]
}
```

## 3. 技术实现清单

| 功能 | 文件改动 | API/页面 |
|------|---------|---------|
| Model Integration | `app/core/config.py`, `.env.example` | 配置增强 |
| Workflow Visual Editor | `app/ui/console.html` | `/studio/workflows` |
| Avatar Upload | `app/ui/routes.py`, `app/api/`, `app/data/avatars/` | `POST /studio/upload` |
| Proposal Notification | `app/ui/console.html` | 所有页面 nav |
| OpenClaw Runtime Bridge | `app/studio/runtime.py`, `app/api/` | `POST /studio/runs/{id}/dispatch` |

## 4. 设计风格借鉴（Multica）

**配色保持现有风格，但借鉴 Multica 的交互模式：**

1. **Agent Card 增强**
   - 添加状态指示器（在线/离线/运行中）
   - 添加进度条（当前任务进度）
   - 添加快捷操作按钮

2. **Timeline 增强**
   - 实时更新运行状态
   - 彩色状态节点
   - 可点击查看详情

3. **Navigation 增强**
   - Badge 通知
   - 下拉菜单（移动端）
   - 快捷搜索

4. **轻量化原则**
   - 不做复杂的组织架构图
   - 聚焦 Issue / Workflow / Agent 三大核心
   - 保持界面简洁清晰

## 5. 下一步

1. ✅ 更新设计文档（本文件）
2. 🔲 Model Integration 实现
3. 🔲 Workflow Visual Editor 实现
4. 🔲 Agent Avatar Upload 实现
5. 🔲 Proposal Notification 实现
6. 🔲 OpenClaw Runtime Bridge 实现
7. 🔲 统一推送到 GitHub

---

*Created: 2026-04-20*
*Inspired by: https://github.com/multica-ai/multica*