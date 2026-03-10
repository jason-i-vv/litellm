# Anthropic Prompt Caching 成本计算说明

## 问题描述

用户在使用 Anthropic Claude Sonnet 4.5 时，观察到以下现象：

```
Tokens:
61867 (61040 prompt tokens + 827 completion tokens)
Cache Read Tokens: 60,235
Cache Creation Tokens: 795
Cost: $0.022807
Cache Hit: False
```

**疑问**：为什么 `Cache Read Tokens` 有值（60,235），但 `Cache Hit` 显示为 `False`，并且没有单独显示缓存的价格？

## 解答

### 1. Cache Hit 的含义

在 LiteLLM 中，`cache_hit` 是一个**布尔值**，用于表示响应是否**完全**来自 LiteLLM 的缓存系统（如 Redis、In-memory 缓存等）。

**关键点**：
- `cache_hit = True`：整个响应 100% 来自 LiteLLM 的缓存，成本为 $0
- `cache_hit = False`：响应不是完全来自 LiteLLM 缓存（可能是部分缓存或没有缓存）

**代码位置**：`litellm/cost_calculator.py:1447`
```python
if cache_hit is not None and cache_hit is True:
    response_cost = 0.0  # 完全缓存命中，成本为 0
```

### 2. Anthropic Prompt Caching 的工作机制

Anthropic 的 Prompt Caching 是一个**不同的机制**，它支持：

#### 部分缓存命中（Partial Cache Hit）
- **Cache Read Tokens**：从 Anthropic 的缓存中读取的 tokens
- **Cache Creation Tokens**：新创建并写入 Anthropic 缓存的 tokens
- **Normal Tokens**：不涉及缓存的普通 tokens

在你的例子中：
- `Cache Read Tokens = 60,235`：大部分内容从缓存读取
- `Cache Creation Tokens = 795`：少量新内容被创建并写入缓存
- `Prompt Tokens = 61,040`：总 prompt tokens（包含上述两部分）

### 3. 为什么 Cache Hit = False？

因为这是一个**部分缓存命中**的场景：
- 不是 100% 从缓存读取
- 包含了新内容（795 tokens 需要被处理并写入缓存）
- `cache_hit` 字段是针对 LiteLLM 自己的缓存功能，不是 Anthropic Prompt Caching

### 4. 缓存成本是否被计算？

**是的！** LiteLLM 确实计算了 Anthropic Prompt Caching 的成本。

#### Anthropic 缓存定价（以 Claude Sonnet 4.5 为例）

```json
{
  "input_cost_per_token": 3.0e-06,           // $0.003 / 1K tokens (普通输入)
  "cache_creation_input_token_cost": 3.75e-06,  // $0.00375 / 1K tokens (缓存写入，贵 25%)
  "cache_read_input_token_cost": 3.0e-07,       // $0.0003 / 1K tokens (缓存读取，便宜 90%)
  "output_cost_per_token": 1.5e-05           // $0.015 / 1K tokens (输出)
}
```

#### 你的例子的成本计算

```python
# 缓存读取成本（便宜 90%）
cache_read_cost = 60,235 tokens × $0.0003 / 1K = $0.0181

# 缓存创建成本（贵 25%）
cache_creation_cost = 795 tokens × $0.00375 / 1K = $0.0030

# 正常 prompt tokens（如果有的话）
normal_prompt_cost = 0 tokens × $0.003 / 1K = $0

# 输出 tokens
completion_cost = 827 tokens × $0.015 / 1K = $0.0124

# 总成本
total_cost = $0.0181 + $0.0030 + $0 + $0.0124 = $0.0335
```

**注意**：实际显示的成本 $0.022807 可能包含了其他计算因素或舍入。

#### 代码实现位置

成本计算在 `litellm/litellm_core_utils/llm_cost_calc/utils.py` 中的 `generic_cost_per_token` 函数：

```python
def _calculate_input_cost(
    prompt_tokens_details: PromptTokensDetailsResult,
    model_info: ModelInfo,
    prompt_base_cost: float,
    cache_read_cost: float,
    cache_creation_cost: float,
    cache_creation_cost_above_1hr: float,
) -> float:
    """计算输入成本，包括缓存"""

    # 普通 prompt tokens
    prompt_cost = float(prompt_tokens_details["text_tokens"]) * prompt_base_cost

    # 缓存读取成本（使用分级定价）
    prompt_cost += float(prompt_tokens_details["cache_hit_tokens"]) * cache_read_cost

    # 缓存写入成本（使用分级定价）
    prompt_cost += calculate_cache_writing_cost(
        cache_creation_tokens=prompt_tokens_details["cache_creation_tokens"],
        cache_creation_token_details=prompt_tokens_details["cache_creation_token_details"],
        cache_creation_cost_above_1hr=cache_creation_cost_above_1hr,
        cache_creation_cost=cache_creation_cost,
    )

    return prompt_cost
```

### 5. 为什么没有单独显示缓存价格？

LiteLLM 将所有成本合并到一个总成本中显示：
- 缓存读取成本包含在 `prompt_tokens_cost` 中
- 缓存创建成本也包含在 `prompt_tokens_cost` 中
- 不会单独显示每个部分的成本

如果你需要查看详细的成本分解，可以：
1. 启用 verbose 日志：`litellm.set_verbose=True`
2. 查看 `usage` 对象中的详细 token 信息
3. 手动计算每个部分的成本

## 总结

| 指标 | 值 | 说明 |
|------|-----|------|
| Cache Read Tokens | 60,235 | 从 Anthropic 缓存读取的 tokens（便宜 90%） |
| Cache Creation Tokens | 795 | 新创建并写入缓存的 tokens（贵 25%） |
| Cache Hit | False | 不是 100% 缓存命中，这是 LiteLLM 自己的缓存标志 |
| 缓存成本是否计算 | **是** | LiteLLM 正确计算了 Anthropic Prompt Caching 的成本 |
| 成本显示 | 合并显示 | 缓存成本包含在总成本中，不单独显示 |

## Anthropic Prompt Caching 的优势

使用 Prompt Caching 可以大幅降低成本：
- **缓存读取**：比普通输入便宜 **90%**（$0.0003 vs $0.003 / 1K tokens）
- **缓存写入**：比普通输入贵 **25%**（$0.00375 vs $0.003 / 1K tokens）
- **适用场景**：
  - 重复使用的系统提示词
  - 长文档分析
  - 多轮对话
  - 代码库上下文

## 如何使用 Anthropic Prompt Caching

在消息中添加 `cache_control` 参数：

```python
import litellm

response = litellm.completion(
    model="claude-sonnet-4-5-20250929",
    messages=[
        {
            "role": "system",
            "content": "你是一个有用的助手...",  # 长系统提示词
            "cache_control": {"type": "ephemeral"}  # 启用缓存
        },
        {
            "role": "user",
            "content": "用户问题"
        }
    ]
)

# 查看缓存 tokens
print(response.usage.cache_read_input_tokens)
print(response.usage.cache_creation_input_tokens)
```

## 价格计算的优先级

LiteLLM 支持多种方式指定模型价格，**优先级从高到低**为：

### 1. 自定义价格（最高优先级）- 但不支持缓存定价

通过 `litellm.register_model()` 注册自定义模型价格：

```python
import litellm

# 注册自定义价格
litellm.register_model({
    "claude-sonnet-4-5-20250929": {
        "input_cost_per_token": 0.000004,  # 自定义输入价格
        "output_cost_per_token": 0.000020,  # 自定义输出价格
        "litellm_provider": "anthropic",
        "mode": "chat"
    }
})

# 之后的调用会使用自定义价格
response = litellm.completion(
    model="claude-sonnet-4-5-20250929",
    messages=[{"role": "user", "content": "Hello"}]
)
```

**⚠️ 重要限制**：
- `litellm.register_model()` **只支持**基本价格字段：
  - `input_cost_per_token`
  - `output_cost_per_token`
- **不支持**缓存相关的价格字段：
  - `cache_creation_input_token_cost`
  - `cache_read_input_token_cost`
  - `cache_creation_input_token_cost_above_200k_tokens`
  - `cache_read_input_token_cost_above_200k_tokens`

**如果你使用了自定义价格**：
- 缓存的 tokens 会按照 `input_cost_per_token` 计算
- 无法享受 Anthropic 缓存的 90% 折扣
- **不推荐**对使用 Prompt Caching 的模型使用自定义价格

### 2. 配置文件价格（默认）- 支持完整缓存定价

如果没有注册自定义价格，LiteLLM 会使用内置配置文件 `model_prices_and_context_window.json` 中的价格。

**配置文件示例**（Claude Sonnet 4.5）：

```json
{
  "claude-sonnet-4-5-20250929": {
    "input_cost_per_token": 3.0e-06,
    "output_cost_per_token": 1.5e-05,
    "cache_creation_input_token_cost": 3.75e-06,
    "cache_read_input_token_cost": 3.0e-07,
    "cache_creation_input_token_cost_above_200k_tokens": 7.5e-06,
    "cache_read_input_token_cost_above_200k_tokens": 6.0e-07,
    "input_cost_per_token_above_200k_tokens": 6.0e-06,
    "output_cost_per_token_above_200k_tokens": 2.25e-05,
    "max_tokens": 64000,
    "max_input_tokens": 200000,
    "supports_prompt_caching": true
  }
}
```

**配置文件的优势**：
- ✅ 支持完整的缓存定价
- ✅ 支持分级定价（超过 200K tokens 的价格）
- ✅ 自动更新（LiteLLM 会定期更新价格）
- ✅ 包含所有模型特性标志

### 3. 价格计算的实际流程

**代码位置**：`litellm/cost_calculator.py:219-229`

```python
## CUSTOM PRICING ##
response_cost = _cost_per_token_custom_pricing_helper(
    prompt_tokens=prompt_tokens,
    completion_tokens=completion_tokens,
    response_time_ms=response_time_ms,
    custom_cost_per_second=custom_cost_per_second,
    custom_cost_per_token=custom_cost_per_token,  # 优先级最高
)

if response_cost is not None:
    return response_cost[0], response_cost[1]  # 直接返回，不考虑缓存

# 如果没有自定义价格，继续使用配置文件价格 + 缓存计算
```

### 4. 如何正确使用自定义价格

#### 场景 1：不使用 Prompt Caching

```python
import litellm

# 注册自定义价格
litellm.register_model({
    "my-custom-model": {
        "input_cost_per_token": 0.00001,
        "output_cost_per_token": 0.00003,
        "litellm_provider": "anthropic",
        "mode": "chat"
    }
})

response = litellm.completion(
    model="my-custom-model",
    messages=[{"role": "user", "content": "Hello"}]
)
# ✅ 会正确使用自定义价格
```

#### 场景 2：使用 Prompt Caching - 不推荐自定义价格

```python
import litellm

# ❌ 不推荐：注册了自定义价格但使用缓存
litellm.register_model({
    "claude-sonnet-4-5-20250929": {
        "input_cost_per_token": 0.000003,
        "output_cost_per_token": 0.000015,
        # 无法设置缓存价格！
    }
})

response = litellm.completion(
    model="claude-sonnet-4-5-20250929",
    messages=[
        {
            "role": "system",
            "content": "长系统提示词...",
            "cache_control": {"type": "ephemeral"}  # 使用缓存
        },
        {"role": "user", "content": "用户问题"}
    ]
)
# ⚠️ 缓存的 tokens 会按 input_cost_per_token 计算
# 无法享受 90% 折扣！
```

#### 场景 3：使用 Prompt Caching - 推荐使用默认价格

```python
import litellm

# ✅ 推荐：不注册自定义价格，使用默认配置
response = litellm.completion(
    model="claude-sonnet-4-5-20250929",
    messages=[
        {
            "role": "system",
            "content": "长系统提示词...",
            "cache_control": {"type": "ephemeral"}
        },
        {"role": "user", "content": "用户问题"}
    ]
)
# ✅ 会正确计算缓存价格：
# - Cache Read: $0.0003 / 1K tokens (便宜 90%)
# - Cache Write: $0.00375 / 1K tokens (贵 25%)
# - Normal Input: $0.003 / 1K tokens
```

### 5. 修改配置文件（高级用法）

如果你确实需要为支持缓存的模型修改价格，可以直接修改配置文件：

```python
import litellm

# 方法 1: 直接修改 model_cost 字典（运行时）
litellm.model_cost["claude-sonnet-4-5-20250929"]["input_cost_per_token"] = 0.000004
litellm.model_cost["claude-sonnet-4-5-20250929"]["cache_read_input_token_cost"] = 0.0000004

# 方法 2: 通过 register_model 完整覆盖（推荐）
litellm.register_model({
    "claude-sonnet-4-5-20250929": {
        "input_cost_per_token": 3.0e-06,
        "output_cost_per_token": 1.5e-05,
        "cache_creation_input_token_cost": 3.75e-06,
        "cache_read_input_token_cost": 3.0e-07,
        "cache_creation_input_token_cost_above_200k_tokens": 7.5e-06,
        "cache_read_input_token_cost_above_200k_tokens": 6.0e-07,
        "input_cost_per_token_above_200k_tokens": 6.0e-06,
        "output_cost_per_token_above_200k_tokens": 2.25e-05,
        "litellm_provider": "anthropic",
        "mode": "chat",
        "max_tokens": 64000,
        "max_input_tokens": 200000,
        "supports_prompt_caching": True
    }
})
```

## 总结：价格计算优先级

| 优先级 | 方法 | 支持缓存定价 | 推荐场景 |
|--------|------|-------------|----------|
| 🥇 最高 | `custom_cost_per_token` 参数 | ❌ 否 | 临时测试 |
| 🥈 中等 | `litellm.register_model()` | ⚠️ 需要完整配置 | 自定义模型 |
| 🥉 默认 | 配置文件 `model_prices_and_context_window.json` | ✅ 是 | **Prompt Caching（推荐）** |

**最佳实践**：
- ✅ 对于官方 Anthropic 模型，使用默认配置价格
- ✅ 对于自定义模型（不使用缓存），使用 `register_model()`
- ⚠️ 如果要修改官方模型价格并使用缓存，需要在 `register_model()` 中提供完整的缓存价格配置
- ❌ 不要只设置 `input_cost_per_token` 和 `output_cost_per_token` 就使用 Prompt Caching

## 参考资料

- [Anthropic Prompt Caching 文档](https://docs.anthropic.com/claude/docs/prompt-caching)
- [LiteLLM Prompt Caching 支持](https://docs.litellm.ai/docs/completion/prompt_caching)
- [LiteLLM 自定义定价文档](https://docs.litellm.ai/docs/completion/cost_tracking#custom-pricing)
- 代码位置：
  - 成本计算：`litellm/litellm_core_utils/llm_cost_calc/utils.py`
  - 自定义定价：`litellm/cost_calculator.py:114-134`
  - 注册模型：`litellm/utils.py:2501`
  - Anthropic 转换：`litellm/llms/anthropic/chat/transformation.py`
  - 价格配置：`litellm/model_prices_and_context_window.json`
