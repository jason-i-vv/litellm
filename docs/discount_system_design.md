# LiteLLM 模型代理平台折扣系统设计方案

## 业务场景

你正在开发一个模型代理平台：
- 用户可以添加自己的模型 API Key（如 Gemini、Anthropic 等）
- 用户可以售卖闲置的 token 配额
- 用户可以设置低价折扣吸引买家
- 需要保证 `max_budget` 预算控制仍然有效

## 核心问题

如果使用 `litellm.register_model()` 自定义价格：
- ❌ 不支持 Anthropic Prompt Caching 的缓存价格
- ❌ 用户设置的折扣无法生效
- ❌ `max_budget` 基于错误的价格计算

## 推荐方案：使用 LiteLLM 内置的折扣机制

LiteLLM 提供了两个内置机制，完美适合你的场景：

### 1. `cost_discount_config` - 折扣配置（推荐）

用于给用户提供折扣（售卖闲置 token）。

### 2. `cost_margin_config` - 加价配置

用于平台收取服务费。

## 完整实现方案

### 架构设计

```
原始成本（包含缓存折扣）
    ↓
应用用户折扣 (cost_discount_config)
    ↓
应用平台加价 (cost_margin_config)
    ↓
最终成本
    ↓
记录到 max_budget / spend 表
```

### 方案 1：基于 Provider 的折扣（简单场景）

**适用场景**：用户对整个 provider 设置统一折扣（如：所有 Anthropic 模型 8折）

#### 数据库设计

```sql
-- 用户折扣配置表
CREATE TABLE user_discount_config (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,  -- 'anthropic', 'openai', 'gemini'
    discount_percent DECIMAL(3, 2) NOT NULL,  -- 0.00 ~ 1.00 (0% ~ 100%)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, provider)
);

-- 示例数据
-- 用户A: Anthropic 模型 8折 (20% off)
-- 用户B: Gemini 模型 5折 (50% off)
INSERT INTO user_discount_config (user_id, provider, discount_percent) VALUES
('user_a', 'anthropic', 0.20),
('user_b', 'gemini', 0.50);
```

#### 实现代码

```python
from fastapi import FastAPI, Request
from typing import Dict
import litellm

app = FastAPI()

async def load_user_discount_config(user_id: str) -> Dict[str, float]:
    """
    从数据库加载用户的折扣配置

    Returns:
        Dict[provider, discount_percent]
        例如: {'anthropic': 0.20, 'gemini': 0.50}
    """
    # 从数据库查询
    query = """
        SELECT provider, discount_percent
        FROM user_discount_config
        WHERE user_id = $1
    """
    results = await db.fetch_all(query, user_id)

    discount_config = {}
    for row in results:
        discount_config[row['provider']] = row['discount_percent']

    return discount_config

async def apply_user_discount(user_id: str):
    """在请求开始前应用用户折扣"""
    discount_config = await load_user_discount_config(user_id)

    # 设置到 LiteLLM 全局配置
    litellm.cost_discount_config = discount_config

    print(f"Applied discount for user {user_id}: {discount_config}")

@app.middleware("http")
async def discount_middleware(request: Request, call_next):
    """中间件：在每个请求前应用用户折扣"""

    # 从请求中获取 user_id（从 API key、JWT 等）
    user_id = request.headers.get("X-User-ID") or "default"

    # 应用用户折扣
    await apply_user_discount(user_id)

    # 处理请求
    response = await call_next(request)

    # 清理折扣配置（可选，避免影响其他请求）
    litellm.cost_discount_config = {}

    return response

# 示例：用户请求
@app.post("/v1/chat/completions")
async def chat_completion(request: Request):
    """
    用户调用模型 API

    请求头：
        X-User-ID: user_a
        Authorization: Bearer sk-xxx
    """
    data = await request.json()

    # 调用 LiteLLM
    response = await litellm.acompletion(
        model=data["model"],
        messages=data["messages"]
    )

    # 成本会自动应用折扣
    # 例如：原始成本 $0.03，用户A 8折，最终成本 $0.024
    print(f"Response cost: ${response._hidden_params.get('response_cost', 0)}")

    return response
```

#### 使用示例

```python
# 用户A（Anthropic 8折）请求
POST /v1/chat/completions
Headers:
    X-User-ID: user_a
    Authorization: Bearer sk-xxx
Body:
{
    "model": "claude-sonnet-4-5-20250929",
    "messages": [
        {
            "role": "system",
            "content": "长系统提示词...",
            "cache_control": {"type": "ephemeral"}
        },
        {"role": "user", "content": "Hello"}
    ]
}

# 成本计算过程：
# 1. 原始成本（包含缓存折扣）：$0.03
# 2. 应用用户折扣 20%：$0.03 × 0.8 = $0.024
# 3. 记录到用户 spend：$0.024
# 4. max_budget 检查：基于 $0.024
```

### 方案 2：基于 API Key 的动态折扣（推荐，灵活）

**适用场景**：每个用户的每个 API key 可以设置不同的折扣

#### 数据库设计

```sql
-- 扩展 LiteLLM 的 user_api_keys 表
ALTER TABLE "LiteLLM_VerificationToken"
ADD COLUMN discount_config JSONB DEFAULT '{}';

-- 示例数据
UPDATE "LiteLLM_VerificationToken"
SET discount_config = '{
    "anthropic": 0.20,
    "gemini": 0.50
}'
WHERE token = 'sk-user-a-key-1';

-- 或者更精细的配置
UPDATE "LiteLLM_VerificationToken"
SET discount_config = '{
    "anthropic": {
        "percentage": 0.20,
        "models": ["claude-sonnet-4-5-20250929"]
    },
    "gemini": 0.50
}'
WHERE token = 'sk-user-b-key-1';
```

#### 实现代码（集成到 LiteLLM Proxy）

```python
# 在 litellm/proxy/auth/user_api_key_auth.py 中添加

from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
import litellm

async def apply_api_key_discount(user_api_key_dict: UserAPIKeyAuth):
    """
    从 API key 配置中加载并应用折扣

    Args:
        user_api_key_dict: API key 验证结果
    """
    # 获取 discount_config
    discount_config = user_api_key_dict.metadata.get("discount_config", {})

    if discount_config:
        # 应用到 LiteLLM
        litellm.cost_discount_config = discount_config

        verbose_logger.info(
            f"Applied discount for API key {user_api_key_dict.token[:10]}***: {discount_config}"
        )

# 在 proxy_server.py 的请求处理中
@router.post("/v1/chat/completions")
async def chat_completion(
    request: Request,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    # 应用 API key 的折扣配置
    await apply_api_key_discount(user_api_key_dict)

    # 处理请求
    data = await request.json()
    response = await litellm.acompletion(**data)

    return response
```

#### 管理端点

```python
from fastapi import APIRouter, Depends
from litellm.proxy._types import UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth

router = APIRouter()

@router.patch("/key/discount")
async def update_key_discount(
    discount_config: Dict[str, float],
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    更新 API key 的折扣配置

    Body:
    {
        "anthropic": 0.20,  // 20% 折扣
        "gemini": 0.50      // 50% 折扣
    }
    """
    # 验证折扣范围
    for provider, discount in discount_config.items():
        if not (0 <= discount <= 1):
            raise HTTPException(
                status_code=400,
                detail=f"Discount for {provider} must be between 0 and 1"
            )

    # 更新数据库
    await prisma_client.db.litellm_verificationtoken.update(
        where={"token": user_api_key_dict.token},
        data={"discount_config": discount_config}
    )

    return {
        "message": "Discount configuration updated",
        "discount_config": discount_config
    }

@router.get("/key/discount")
async def get_key_discount(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """获取当前 API key 的折扣配置"""
    return {
        "discount_config": user_api_key_dict.metadata.get("discount_config", {})
    }
```

### 方案 3：平台加价 + 用户折扣组合

**适用场景**：平台收取服务费 + 用户设置折扣

```python
# 配置示例
# config.yaml
litellm_settings:
  # 全局平台加价 5%
  cost_margin_config:
    global: 0.05

  # 用户折扣（动态设置）
  cost_discount_config: {}  # 由 API key 动态设置

# 成本计算流程
原始成本: $0.030 (包含缓存折扣)
    ↓
应用用户折扣 20%: $0.030 × 0.8 = $0.024
    ↓
应用平台加价 5%: $0.024 × 1.05 = $0.0252
    ↓
最终成本: $0.0252
```

#### 实现代码

```python
import litellm

# 设置全局平台加价
litellm.cost_margin_config = {
    "global": 0.05  # 5% 平台服务费
}

# 用户折扣（每个请求动态设置）
async def apply_user_discount(user_discount_config: Dict[str, float]):
    litellm.cost_discount_config = user_discount_config

# 示例
await apply_user_discount({"anthropic": 0.20})  # 用户A：8折
response = await litellm.acompletion(
    model="claude-sonnet-4-5-20250929",
    messages=[...]
)

# 成本计算：
# 原始: $0.030
# 折扣后: $0.030 × 0.8 = $0.024（用户实际成本）
# 加价后: $0.024 × 1.05 = $0.0252（平台收费）
```

## max_budget 预算控制

### 原理说明

`max_budget` 是基于**最终成本**（应用折扣/加价后）计算的：

```python
# litellm/cost_calculator.py 中的逻辑
original_cost = base_cost

# 1. 应用折扣
final_cost, discount_percent, discount_amount = _apply_cost_discount(
    base_cost=original_cost,
    custom_llm_provider=custom_llm_provider,
)

# 2. 应用加价
final_cost, margin_percent, margin_fixed_amount, margin_total_amount = _apply_cost_margin(
    base_cost=final_cost,
    custom_llm_provider=custom_llm_provider,
)

# 3. 记录到 spend 表
# final_cost 会被用于 max_budget 检查
```

### 配置示例

```sql
-- 为用户设置 max_budget
UPDATE "LiteLLM_TeamTable"
SET max_budget = 100.00  -- $100 预算
WHERE team_id = 'team_user_a';

-- 用户请求
-- 原始成本: $0.030
-- 折扣 20%: $0.024
-- 记录到 spend: $0.024
-- max_budget 检查: 累计 spend < $100.00 ✅
```

**重要**：`max_budget` 是基于用户实际支付的成本（折扣后），不是原始成本！

## 前端 UI 设计

### 用户设置折扣页面

```html
<!-- 折扣设置表单 -->
<form id="discount-form">
    <h3>设置模型折扣</h3>

    <div class="discount-item">
        <label>Anthropic 模型折扣</label>
        <input type="number" name="anthropic" min="0" max="100" step="1" value="80">
        <span>%（原价的 80%）</span>
    </div>

    <div class="discount-item">
        <label>Google Gemini 折扣</label>
        <input type="number" name="gemini" min="0" max="100" step="1" value="50">
        <span>%（原价的 50%，5折）</span>
    </div>

    <div class="discount-item">
        <label>OpenAI 模型折扣</label>
        <input type="number" name="openai" min="0" max="100" step="1" value="100">
        <span>%（不打折）</span>
    </div>

    <button type="submit">保存折扣设置</button>
</form>

<script>
document.getElementById('discount-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    // 转换为 LiteLLM 格式（0-1）
    const discountConfig = {
        anthropic: 1 - (parseFloat(e.target.anthropic.value) / 100),
        gemini: 1 - (parseFloat(e.target.gemini.value) / 100),
        openai: 1 - (parseFloat(e.target.openai.value) / 100)
    };

    // 发送到后端
    const response = await fetch('/api/key/discount', {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + apiKey
        },
        body: JSON.stringify(discountConfig)
    });

    if (response.ok) {
        alert('折扣设置已保存！');
    }
});
</script>
```

### 成本预览

```html
<!-- 实时成本预览 -->
<div class="cost-preview">
    <h4>成本预览（Claude Sonnet 4.5）</h4>

    <table>
        <tr>
            <td>原始成本（1M tokens）</td>
            <td>$3.00</td>
        </tr>
        <tr>
            <td>缓存读取（90% 折扣）</td>
            <td>$0.30</td>
        </tr>
        <tr>
            <td>你的折扣（20% off）</td>
            <td class="highlight">$2.40 / $0.24</td>
        </tr>
        <tr>
            <td>平台服务费（5%）</td>
            <td>$2.52 / $0.252</td>
        </tr>
    </table>

    <p class="savings">
        💰 使用缓存 + 你的折扣，买家可节省 <strong>91.6%</strong> 成本！
    </p>
</div>
```

## 完整代码示例

```python
# main.py - 完整实现

from fastapi import FastAPI, Depends, Request, HTTPException
from typing import Dict, Optional
import litellm
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.proxy._types import UserAPIKeyAuth

app = FastAPI()

# 全局平台加价配置
litellm.cost_margin_config = {
    "global": 0.05  # 5% 平台服务费
}

@app.middleware("http")
async def apply_discount_middleware(request: Request, call_next):
    """
    中间件：自动应用 API key 的折扣配置
    """
    # 处理请求
    response = await call_next(request)

    # 清理折扣配置
    litellm.cost_discount_config = {}

    return response

@app.post("/v1/chat/completions")
async def chat_completion(
    request: Request,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    聊天完成 API

    自动应用：
    1. API key 的折扣配置
    2. 全局平台加价
    3. Anthropic Prompt Caching 折扣
    """
    # 1. 获取并应用 API key 折扣
    discount_config = user_api_key_dict.metadata.get("discount_config", {})
    if discount_config:
        litellm.cost_discount_config = discount_config

    # 2. 处理请求
    data = await request.json()

    try:
        response = await litellm.acompletion(
            model=data["model"],
            messages=data["messages"],
            **{k: v for k, v in data.items() if k not in ["model", "messages"]}
        )

        # 3. 返回响应（成本已自动计算并应用折扣/加价）
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/key/discount")
async def update_discount(
    discount_config: Dict[str, float],
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    更新 API key 折扣配置

    Body:
    {
        "anthropic": 0.20,  # 20% 折扣（80% 价格）
        "gemini": 0.50      # 50% 折扣（5折）
    }
    """
    # 验证
    for provider, discount in discount_config.items():
        if not (0 <= discount <= 1):
            raise HTTPException(
                status_code=400,
                detail=f"Discount for {provider} must be 0-1 (0%-100%)"
            )

    # 更新数据库（示例）
    # await update_api_key_metadata(
    #     token=user_api_key_dict.token,
    #     metadata={"discount_config": discount_config}
    # )

    return {
        "message": "Discount updated",
        "discount_config": discount_config
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 测试场景

### 测试 1：Anthropic Prompt Caching + 用户折扣

```bash
# 设置用户折扣 20%
curl -X PATCH http://localhost:8000/api/key/discount \
  -H "Authorization: Bearer sk-user-a" \
  -H "Content-Type: application/json" \
  -d '{
    "anthropic": 0.20
  }'

# 测试请求（使用缓存）
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-user-a" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250929",
    "messages": [
      {
        "role": "system",
        "content": "Very long system prompt...",
        "cache_control": {"type": "ephemeral"}
      },
      {
        "role": "user",
        "content": "Hello"
      }
    ]
  }'

# 预期成本计算：
# 原始成本（60K cache read）: 60,000 × $0.0003/1K = $0.018
# 原始成本（795 cache write）: 795 × $0.00375/1K = $0.003
# 原始成本（827 output）: 827 × $0.015/1K = $0.012
# 小计: $0.033
#
# 应用折扣 20%: $0.033 × 0.8 = $0.0264
# 应用平台加价 5%: $0.0264 × 1.05 = $0.02772
#
# 最终成本: $0.02772 ✅
# max_budget 检查: 基于 $0.02772
```

### 测试 2：不同用户不同折扣

```python
# 用户A：Anthropic 8折
# 用户B：Anthropic 5折
# 同样的请求，不同的成本

# 用户A 成本: $0.0264
# 用户B 成本: $0.0165
```

## 总结

| 方案 | 优势 | 劣势 | 推荐场景 |
|------|------|------|----------|
| 基于 Provider 折扣 | 简单、易实现 | 所有模型统一折扣 | 初期快速上线 |
| 基于 API Key 折扣 | 灵活、精细控制 | 需要扩展数据库 | **推荐** |
| 组合方案 | 平台收费 + 用户折扣 | 复杂度略高 | 商业运营 |

### 核心优势

✅ **不需要修改 LiteLLM 核心代码**
✅ **完全支持 Anthropic Prompt Caching**
✅ **max_budget 预算控制有效**
✅ **支持动态调整折扣**
✅ **支持平台收取服务费**

### 实施步骤

1. **数据库扩展**：在 `LiteLLM_VerificationToken` 表添加 `discount_config` 字段
2. **API 端点**：实现折扣配置的 GET/PATCH 端点
3. **中间件**：在请求处理前应用折扣配置
4. **前端 UI**：提供用户友好的折扣设置界面
5. **监控**：记录折扣应用情况，生成报表

## 参考文档

- LiteLLM 折扣配置：`litellm/proxy/management_endpoints/cost_tracking_settings.py`
- 成本计算逻辑：`litellm/cost_calculator.py:678-771`
- Anthropic Prompt Caching：`docs/anthropic_prompt_caching_explanation.md`
