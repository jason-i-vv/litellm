#!/usr/bin/env python3
"""
LiteLLM Model-Level Discount Enablement Script

这个脚本会自动修改 litellm/cost_calculator.py 以支持 model 级别的折扣配置。

修改内容：
1. _apply_cost_discount 函数增加 model 参数
2. 优先检查 model 级别折扣，然后才是 provider 级别
3. 更新所有调用处传入 model 参数

使用方法：
    python scripts/enable_model_level_discount.py

回滚方法：
    git checkout litellm/cost_calculator.py
"""

import re
import sys
from pathlib import Path


def patch_cost_calculator():
    """应用补丁以支持 model 级别折扣"""

    file_path = Path(__file__).parent.parent / "litellm" / "cost_calculator.py"

    if not file_path.exists():
        print(f"❌ 错误: 找不到文件 {file_path}")
        sys.exit(1)

    print(f"📝 正在修改 {file_path}...")

    # 读取文件
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # ========== 修改 1: 更新函数签名 ==========
    print("🔧 步骤 1/4: 更新函数签名...")

    old_sig = """def _apply_cost_discount(
    base_cost: float,
    custom_llm_provider: Optional[str],
) -> Tuple[float, float, float]:"""

    new_sig = """def _apply_cost_discount(
    base_cost: float,
    custom_llm_provider: Optional[str],
    model: Optional[str] = None,
) -> Tuple[float, float, float]:"""

    if old_sig in content:
        content = content.replace(old_sig, new_sig)
        print("   ✅ 函数签名已更新")
    else:
        print("   ⚠️  函数签名可能已被修改，跳过")
        # 检查是否已经应用过补丁
        if "model: Optional[str] = None," in content:
            print("   ℹ️  检测到补丁可能已应用")

    # ========== 修改 2: 更新文档字符串 ==========
    print("🔧 步骤 2/4: 更新文档字符串...")

    old_docstring = '''    """
    Apply provider-specific cost discount from module-level config.

    Args:
        base_cost: The base cost before discount
        custom_llm_provider: The LLM provider name

    Returns:
        Tuple of (final_cost, discount_percent, discount_amount)
    """'''

    new_docstring = '''    """
    Apply provider-specific or model-specific cost discount from module-level config.

    Args:
        base_cost: The base cost before discount
        custom_llm_provider: The LLM provider name
        model: The model name (for model-specific discounts)

    Returns:
        Tuple of (final_cost, discount_percent, discount_amount)
    """'''

    if old_docstring in content:
        content = content.replace(old_docstring, new_docstring)
        print("   ✅ 文档字符串已更新")
    else:
        print("   ⚠️  文档字符串可能已被修改，跳过")

    # ========== 修改 3: 添加 model 级别折扣逻辑 ==========
    print("🔧 步骤 3/4: 添加 model 级别折扣逻辑...")

    old_logic = """    original_cost = base_cost
    discount_percent = 0.0
    discount_amount = 0.0

    if custom_llm_provider and custom_llm_provider in litellm.cost_discount_config:
        discount_percent = litellm.cost_discount_config[custom_llm_provider]
        discount_amount = original_cost * discount_percent
        final_cost = original_cost - discount_amount

        verbose_logger.debug(
            f"Applied {discount_percent*100}% discount to {custom_llm_provider}: "
            f"${original_cost:.6f} -> ${final_cost:.6f} (saved ${discount_amount:.6f})"
        )

        return final_cost, discount_percent, discount_amount

    return base_cost, discount_percent, discount_amount"""

    new_logic = """    original_cost = base_cost
    discount_percent = 0.0
    discount_amount = 0.0

    # 优先检查 model 级别折扣
    if model and model in litellm.cost_discount_config:
        discount_percent = litellm.cost_discount_config[model]
        discount_amount = original_cost * discount_percent
        final_cost = original_cost - discount_amount

        verbose_logger.debug(
            f"Applied {discount_percent*100}% discount to model {model}: "
            f"${original_cost:.6f} -> ${final_cost:.6f} (saved ${discount_amount:.6f})"
        )

        return final_cost, discount_percent, discount_amount

    # Provider 级别折扣（作为后备）
    if custom_llm_provider and custom_llm_provider in litellm.cost_discount_config:
        discount_percent = litellm.cost_discount_config[custom_llm_provider]
        discount_amount = original_cost * discount_percent
        final_cost = original_cost - discount_amount

        verbose_logger.debug(
            f"Applied {discount_percent*100}% discount to {custom_llm_provider}: "
            f"${original_cost:.6f} -> ${final_cost:.6f} (saved ${discount_amount:.6f})"
        )

        return final_cost, discount_percent, discount_amount

    return base_cost, discount_percent, discount_amount"""

    # 检查是否已经应用过补丁
    if "# 优先检查 model 级别折扣" in content:
        print("   ℹ️  model 级别折扣逻辑已存在，跳过")
    elif old_logic in content:
        content = content.replace(old_logic, new_logic)
        print("   ✅ model 级别折扣逻辑已添加")
    else:
        print("   ⚠️  未找到匹配的逻辑块，可能已被修改")

    # ========== 修改 4: 更新所有调用处 ==========
    print("🔧 步骤 4/4: 更新调用处...")

    # 查找所有 _apply_cost_discount 的调用
    pattern = r'(_apply_cost_discount\(\s*base_cost=[^,]+,\s*custom_llm_provider=[^)]*\))'

    def add_model_param(match):
        """在调用处添加 model 参数"""
        call = match.group(1)
        if 'model=' in call:
            return call  # 已经有 model 参数
        # 移除最后的 )，添加 model 参数
        return call.rstrip(')') + ', model=model)'

    new_content = re.sub(pattern, add_model_param, content)

    if new_content != content:
        content = new_content
        print("   ✅ 调用处已更新")
    else:
        print("   ℹ️  没有找到需要更新的调用处，或已更新")

    # ========== 检查是否有修改 ==========
    if content == original_content:
        print("\n⚠️  没有应用任何修改（可能已经应用过补丁）")
        return

    # ========== 写回文件 ==========
    print(f"\n💾 正在保存修改...")

    # 创建备份
    backup_path = file_path.with_suffix('.py.backup')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(original_content)
    print(f"✅ 备份已创建: {backup_path}")

    # 写入修改后的内容
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ 修改已保存")

    # ========== 验证修改 ==========
    print("\n🔍 验证修改...")

    # 检查关键修改点
    checks = [
        ("model 参数", "model: Optional[str] = None," in content),
        ("model 级别折扣逻辑", "# 优先检查 model 级别折扣" in content),
        ("provider 后备逻辑", "# Provider 级别折扣（作为后备）" in content),
    ]

    all_passed = True
    for check_name, result in checks:
        if result:
            print(f"   ✅ {check_name}")
        else:
            print(f"   ❌ {check_name} 未找到")
            all_passed = False

    if all_passed:
        print("\n✅ 所有验证通过！")
        print("\n🎉 成功！现在 litellm 支持 model 级别折扣了！")
        print("\n📚 使用示例：")
        print("""
   import litellm

   # 设置 model 级别折扣
   litellm.cost_discount_config = {
       "claude-sonnet-4-5-20250929": 0.20,  # Claude Sonnet 4.5: 8折
       "claude-opus-4-20250514": 0.10,      # Claude Opus 4: 9折
       "anthropic": 0.25,                    # 其他 Anthropic 模型: 75折
   }

   # 调用 API（自动应用折扣）
   response = await litellm.acompletion(
       model="claude-sonnet-4-5-20250929",
       messages=[...]
   )
        """)
    else:
        print("\n⚠️  部分验证未通过，请检查修改")
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 60)
    print("LiteLLM Model-Level Discount Enablement Script")
    print("=" * 60)
    print()

    try:
        patch_cost_calculator()
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)