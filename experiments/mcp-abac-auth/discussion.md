# MCP ABAC Authorization - 设计讨论

## 💬 设计讨论

### 问题背景

在 MCP（Model Context Protocol）架构中，LLM 需要通过工具（Tools）与外部系统交互。工具通常都可以访问用户的资源，**基础的访问授权由 Token 等 Authorization 机制控制**。

然而，我们需要一个更细粒度的权限控制机制，**针对具体资源的操作进行分开授权控制**。这是因为：

1. **资源级别的权限控制需求**：用户可能希望对某些资源的某些操作可以自由执行（无需多次确认），但对其他资源的相同操作需要授权
2. **防止误操作**：避免 LLM 在获得某个资源的操作授权后，错误地对其他资源执行相同操作
3. **上下文相关的授权**：授权应该与 Chat Context 绑定，不同会话需要重新授权

### 核心场景

**场景示例**：在一个 Chat Context 中，用户可以授权对某一个 Resource ID 的 Tool 的无需二次授权的直接执行。

- ✅ **同一 Chat Context + 同一 Resource ID + 已授权 Tool**：无需再次授权，直接执行
- ❌ **不同 Chat Context**：需要重新授权
- ❌ **同一 Chat Context + 不同 Resource ID + 相同 Tool**：需要授权

**实现目标**：

1. **提升用户体验**：对于某些 update/delete 操作，在某些 resource 上，用户认为可以自由执行，不希望要多次确认
2. **防止意外操作**：避免一些 update/delete 操作被终端授权之后，LLM 错误地提出了 delete 一些其他资源的操作，而由于对 delete tool 授权了，最终造成意外的 action

### 核心设计思路

#### 1. Executor 作为权限决策中心

在 MCP 架构中，**Executor（执行器）** 扮演了关键角色：

- **协调 LLM 和 MCP Client**：Executor 接收 LLM 的工具调用意图，并通过 MCP Client 与 MCP Server 通信
- **权限决策点**：Executor 是进行权限决策的最佳位置，因为：
  - 它了解用户上下文（免再授权的工具执行）
  - 它了解工具特性（通过 MCP Tool Annotations）
  - 它了解操作上下文（请求内容、时间、资源状态等）
- **用户交互接口**：当需要授权时，Executor 可以直接与用户交互，请求确认

#### 2. 利用 MCP Tool Annotations 识别风险

MCP Tool Annotations 提供了标准化的工具元数据，帮助 Executor 做出权限决策：

- **`readOnlyHint`**：标识工具是否为只读操作
  - 只读操作通常风险较低，可以根据策略自动执行
  - 非只读操作需要更严格的权限检查
  
- **`destructiveHint`**：标识工具是否为破坏性操作
  - 破坏性操作（如删除、修改关键配置）应该默认需要用户显式授权
  - 即使通过了权限策略检查，也应该向用户确认

- **`idempotentHint`**：标识工具是否幂等
  - 幂等操作可以更安全地重试
  - 非幂等操作需要更谨慎的处理

- **`openWorldHint`**：标识工具是否与外部系统交互
  - 外部系统交互可能涉及数据泄露或费用产生
  - 需要额外的权限控制和审计

#### 3. ABAC 策略引擎 - 资源级别的权限控制

使用 **ABAC（Attribute-Based Access Control）** 策略引擎实现**资源级别的细粒度权限控制**：

- **资源级别的授权**：权限控制不是针对工具（Tool）本身，而是针对**工具对特定资源（Resource）的操作**
  - 基础授权：工具访问用户资源由 Token 等 Authorization 机制控制（由 MCP Server 处理）
  - 细粒度授权：本策略控制的是**对具体资源的操作权限**，由 Executor 在终端应用层实现

- **策略驱动**：权限规则通过策略文件定义，与代码解耦
- **由 Server 建议**：Server 端提供 tool ABAC 策略建议，由 Executor 自主决定如何使用，最终可以由用户控制如何应用

- **动态决策**：策略引擎根据当前上下文动态评估权限，支持基于以下维度的判断：
  - **资源标识**（Resource ID）：操作的目标资源
  - **工具类型**（Tool）：执行的操作类型
  - **Chat Context**：当前会话上下文
  - **用户授权记录**：用户在该 Chat Context 中对特定 Resource ID 的 Tool 授权记录

- **授权作用域**：
  - 授权记录绑定到：`(Chat Context, Resource ID, Tool)` 三元组
  - 不同 Chat Context 需要重新授权
  - 同一 Chat Context 中，不同 Resource ID 需要分别授权

#### 4. 权限决策流程

典型的权限决策流程如下：

1. **LLM 返回工具调用意图**：LLM 分析用户请求，决定需要调用的工具和操作的目标资源（Resource ID）
2. **Executor 获取工具信息**：通过 MCP Client 从 MCP Server 获取工具定义和 annotations
3. **Executor 提取资源标识**：从工具调用参数中提取目标 Resource ID
4. **Executor 评估策略**：
   - 检查工具的 `readOnlyHint` 和 `destructiveHint`
   - 查询授权记录：检查当前 Chat Context 中，是否已有 `(当前 Chat Context, Resource ID, Tool)` 的授权记录
   - 如果没有授权记录，且工具是破坏性的或策略要求用户确认，则向用户请求授权
5. **用户授权（如需要）**：
   - Executor 向用户展示：工具名称、目标资源 ID、操作类型
   - 用户可以选择：
     - **批准**：记录授权 `(Chat Context, Resource ID, Tool)`，并执行工具调用
     - **拒绝**：终止操作
     - **修改参数**：修改操作参数后重新评估
6. **执行工具调用**：获得授权后，Executor 通过 MCP Client 执行工具调用
7. **返回结果**：工具执行结果通过 Executor 返回给用户

**关键点**：
- 授权记录是**资源级别的**：`(Chat Context, Resource ID, Tool)` 三元组
- 不同 Resource ID 需要分别授权，即使使用相同的 Tool
- 不同 Chat Context 需要重新授权
- 这确保了 LLM 即使获得了某个资源的操作授权，也无法对其他资源执行相同操作

### 架构优势

- **灵活性**：终端应用可以根据自身需求定制权限策略，不依赖 MCP Server 的实现
- **可扩展性**：支持复杂的权限规则和条件判断，易于添加新的权限维度
- **可维护性**：策略与代码分离，权限规则的更新不需要修改代码
- **安全性**：细粒度的权限控制，支持多租户、多用户的复杂场景
- **用户体验**：通过 annotations 和策略，智能地决定何时需要用户确认，避免过度打扰

### 待解决的问题

1. **策略定义标准**：需要定义一套标准的策略定义格式，便于不同应用使用
2. **工具 annotations 的信任**：如何确保工具 annotations 的准确性？是否需要验证机制？
3. **策略冲突处理**：当多个策略规则冲突时，如何处理？
4. **审计和日志**：如何记录权限决策过程，便于审计和问题排查？

## 📖 参考信息

### 1. MCP Tool Annotations

**文章**：[MCP Tool Annotations: Adding Metadata and Context to Your AI Tools](https://blog.marcnuri.com/mcp-tool-annotations-introduction#available-mcp-tool-annotations)

**关键要点**：
- MCP Tool Annotations 是 MCP 规范中引入的元数据机制
- 提供了标准化的工具行为描述方式
- 主要 annotations：
  - `title`：工具的人类可读标题
  - `readOnlyHint`：标识工具是否为只读操作
  - `destructiveHint`：标识工具是否为破坏性操作（仅对非只读工具有效）
  - `idempotentHint`：标识工具是否幂等
  - `openWorldHint`：标识工具是否与外部系统交互
- Annotations 是**建议性提示**，不强制执行，但可以帮助客户端做出更好的决策

**实际应用**：
- 客户端可以根据 annotations 实现安全控制和用户确认机制

### 2. MCP Server Capabilities 和 Tool Annotations 改进建议

**讨论**：[Improvements to Server Capabilities and additional Tool Annotations](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/1138)

**关键要点**：

#### Server Capabilities 改进建议

1. **Provider Information（提供者信息）**：
   - 建议在服务器初始化时传递创建 MCP Server 的组织名称和 URL
   - 客户端可能希望限制只使用特定组织提供的服务器（出于法律或质量考虑）
   - 可能需要区分创建 MCP 的组织和提供/托管 MCP 的组织

2. **Additional Server Capabilities（额外服务器能力）**：
   - `Resource Templates`：基于是否设置了 `ListResourceTemplates` 处理器来表达对资源模板的支持
   - `Completion`：基于是否设置了 `Complete` 处理器来表达对补全的支持

## 🎯 设计思路总结

### 核心问题

1. **资源级别的权限控制**：如何实现对具体资源的操作进行分开授权控制？
2. **防止误操作**：如何避免 LLM 在获得某个资源的操作授权后，错误地对其他资源执行相同操作？
3. **上下文相关的授权**：如何实现授权与 Chat Context 绑定，不同会话需要重新授权？

### 解决方案

1. **资源级别的 ABAC 策略控制**：
   - **基础授权**：工具访问用户资源由 Token 等 Authorization 机制控制（MCP Server 层）
   - **细粒度授权**：对具体资源的操作权限由 Executor 在终端应用层控制
   - 授权记录绑定到 `(Chat Context, Resource ID, Tool)` 三元组
   - 不同 Resource ID 需要分别授权，即使使用相同的 Tool
   - 不同 Chat Context 需要重新授权

2. **利用 MCP Tool Annotations 识别风险**：
   - 通过 `readOnlyHint` 和 `destructiveHint` 识别高风险操作
   - 破坏性操作默认需要用户授权
   - 只读操作可以自动执行（根据策略）

3. **Executor 层决策**：
   - 权限决策在 Executor（终端应用）层完成
   - Executor 从 LLM 获取工具调用意图和目标 Resource ID
   - Executor 检查当前 Chat Context 中是否已有该 `(Chat Context, Resource ID, Tool)` 的授权记录
   - 如果没有授权记录，且工具是破坏性的或策略要求用户确认，则向用户请求授权
   - 用户授权后，记录授权信息，允许后续在该 Chat Context 中对同一 Resource ID 执行相同 Tool 时无需再次授权

### 架构优势

- **资源级别的细粒度控制**：授权精确到 `(Chat Context, Resource ID, Tool)` 级别，避免误操作
- **用户体验优化**：用户可以对特定资源的特定操作授权，后续无需多次确认
- **安全性**：即使 LLM 获得了某个资源的操作授权，也无法对其他资源执行相同操作
- **上下文隔离**：不同 Chat Context 的授权相互独立，提高了安全性
- **灵活性**：终端应用可以根据自身需求定制权限策略，不依赖 MCP Server 的实现
- **可维护性**：策略与代码分离，权限规则的更新不需要修改代码

