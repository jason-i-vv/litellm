# Model 级别折扣功能实现文档

## 功能说明

本功能允许为数据库中的每个 model 对象设置独立的折扣，折扣配置保存在 `model_info` 字段中。系统会在处理请求时自动从数据库读取折扣配置并应用到成本计算中。

## 实现概述

### 修改的文件

1. **litellm/cost_calculator.py**
   - 修改 `_apply_cost_discount` 函数，支持 model 级别的折扣
   - 优先级：model 级别 > provider 级别

2. **litellm/proxy/common_request_processing.py**
   - 添加 `apply_model_discount_by_name` 辅助函数
   - 在请求处理前从数据库读取并应用折扣
   - 请求完成后恢复配置

## 数据库配置

### 设置 Model 折扣

在 `LiteLLM_ProxyModelTable` 表的 `model_info` 字段中设置折扣：

```sql
-- 示例 1：为 Claude Sonnet 4.5 设置 20% 折扣
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = '{
    "discount": 0.20,
    "description": "20% discount for Claude Sonnet 4.5"
}'
WHERE model_name = 'claude-sonnet-4-5-20250929';

-- 示例 2：为 Gemini Flash 设置 50% 折扣
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = '{
    "discount": 0.50,
    "description": "50% discount for Gemini Flash"
}'
WHERE model_name = 'gemini-2.0-flash-exp';

-- 示例 3：通过 model_id 设置
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = '{
    "discount": 0.15,
    "description": "15% discount"
}'
WHERE model_id = 'your-model-id-here';
```

### model_info 字段格式

`model_info` 是一个 JSON 字段（可以是 JSONB 或 JSON 字符串），支持以下格式：

```json
{
    "discount": 0.20,
    "description": "可选的描述信息",
    "other_key": "其他配置"
}
```

**重要字段**：
- `discount`: 折扣率（0.0 - 1.0）
  - 0.0 = 无折扣
  - 0.1 = 9折（10% off）
  - 0.2 = 8折（20% off）
  - 0.5 = 5折（50% off）
  - 1.0 = 免费

## 工作流程

### 请求处理流程

```
1. 用户发起请求
   ↓
2. 获取 model_name
   ↓
3. 从数据库查询 model_info
   ↓
4. 提取 discount 配置
   ↓
5. 设置 litellm.cost_discount_config[model_name] = discount
   ↓
6. 调用 litellm.completion()
   ↓
7. 成本计算时自动应用折扣
   ↓
8. 恢复原始 cost_discount_config
   ↓
9. 返回响应
```

### 成本计算优先级

```
1. 原始成本（包含 Prompt Caching 折扣）
   ↓
2. 应用 Model 级别折扣（从数据库读取）
   ↓
3. 应用 Provider 级别折扣（如果配置了）
   ↓
4. 应用平台加价（如果配置了）
   ↓
5. 最终成本
```

## 使用示例

### 示例 1：为不同模型设置不同折扣

```sql
-- 为 Anthropic 模型设置 20% 折扣
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = '{"discount": 0.20}'
WHERE model_name LIKE 'claude-%';

-- 为 Gemini 模型设置 50% 折扣
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = '{"discount": 0.50}'
WHERE model_name LIKE 'gemini-%';

-- 为 OpenAI 模型设置 10% 折扣
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = '{"discount": 0.10}'
WHERE model_name LIKE 'gpt-%';
```

### 示例 2：查询所有设置了折扣的模型

```sql
SELECT
    model_id,
    model_name,
    model_info->>'discount' as discount_percent,
    model_info->>'description' as description
FROM "LiteLLM_ProxyModelTable"
WHERE model_info IS NOT NULL
  AND model_info->>'discount' IS NOT NULL;
```

### 示例 3：清除某个模型的折扣

```sql
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = model_info - 'discount'
WHERE model_name = 'claude-sonnet-4-5-20250929';

-- 或者完全清空 model_info
UPDATE "LiteLLM_ProxyModelTable"
SET model_info = NULL
WHERE model_name = 'claude-sonnet-4-5-20250929';
```

## 日志输出

当折扣被应用时，会在日志中输出：

```
INFO: Applied 20.0% discount to model 'claude-sonnet-4-5-20250929' (model_id=xxx) from database model_info
```

如果折扣值无效，会输出警告：

```
WARNING: Invalid discount value 1.5 for model 'claude-sonnet-4-5-20250929'. Must be between 0 and 1.
```

## 测试

### 测试脚本

```bash
# 1. 设置折扣
curl -X POST http://localhost:4000/model/update \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "claude-sonnet-4-5-20250929",
    "model_info": {"discount": 0.20}
  }'

# 2. 发送请求
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250929",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# 3. 检查响应头中的成本信息
# x-litellm-response-cost 应该显示折扣后的成本
```

### 验证成本计算

```python
import litellm

# 设置日志级别为 DEBUG 以查看详细信息
litellm.set_verbose = True

# 发送请求
response = litellm.completion(
    model="claude-sonnet-4-5-20250929",
    messages=[{"role": "user", "content": "Hello"}]
)

# 检查成本
print(f"Response cost: ${response._hidden_params.get('response_cost', 0)}")
```

## 注意事项

1. **折扣值范围**：必须在 0.0 到 1.0 之间
2. **数据库查询性能**：每次请求都会查询数据库，建议为 `model_name` 字段添加索引
3. **多实例部署**：如果有多个 Proxy 实例，确保它们连接到同一个数据库
4. **配置优先级**：
   - Model 级别折扣（数据库）> Provider 级别折扣（全局配置）
5. **Prompt Caching**：折扣会在 Prompt Caching 的基础上应用

## 性能优化建议

### 添加数据库索引

```sql
-- 为 model_name 添加索引以提升查询性能
CREATE INDEX IF NOT EXISTS idx_proxy_model_table_model_name
ON "LiteLLM_ProxyModelTable"(model_name);

-- 为 model_info 添加 GIN 索引（如果使用 JSONB）
CREATE INDEX IF NOT EXISTS idx_proxy_model_table_model_info
ON "LiteLLM_ProxyModelTable" USING GIN (model_info);
```

### 缓存策略

如果担心数据库查询性能，可以考虑：

1. 在 Proxy 启动时预加载所有 model 的折扣配置到内存
2. 使用 Redis 缓存 model 的折扣配置
3. 定期刷新缓存

## 故障排查

### 折扣没有生效

1. 检查数据库中的 `model_info` 是否正确设置
2. 检查 Proxy 日志中是否有错误信息
3. 验证 `model_name` 是否匹配
4. 确认折扣值在 0.0-1.0 范围内

### 数据库查询慢

1. 添加索引到 `model_name` 字段
2. 检查数据库连接池配置
3. 考虑使用缓存策略

### max_budget 问题

由于折扣是在请求处理过程中应用的，`max_budget` 的检查会基于折扣后的成本，这是正确的行为。

## 相关文档

- [Anthropic Prompt Caching 说明](./anthropic_prompt_caching_explanation.md)
- [折扣系统设计方案](./discount_system_design.md)
- LiteLLM 官方文档：https://docs.litellm.ai/

## 代码位置

- 成本计算：`litellm/cost_calculator.py:678-728`
- 折扣应用：`litellm/proxy/common_request_processing.py:272-327, 674-691, 843`
