# 模型列表升级说明

## 概述
升级了 `config.py` 中的支持模型列表，添加了所有 AWS Bedrock 批处理支持的最新 Claude 和 Amazon Nova 模型。

## 新增模型

### 文本模式（TEXT_MODELS）

#### Claude 3.5 系列
- **Claude 3.5 Haiku** - 更快的 3.5 版本
  - 模型ID: `anthropic.claude-3-5-haiku-20241022-v1:0`
- **Claude 3.5 Sonnet** - 更新的标准版本
  - 模型ID: `anthropic.claude-3-5-sonnet-20240620-v1:0`

#### Claude 3.7 系列
- **Claude 3.7 Sonnet** - 最新的 Sonnet 版本，增强推理能力
  - 模型ID: `anthropic.claude-3-7-sonnet-20250219-v1:0`

#### Claude 4.x 系列
- **Claude Haiku 4.5** - 最新快速模型
  - 模型ID: `anthropic.claude-haiku-4-5-20251001-v1:0`
- **Claude Sonnet 4** - 最新标准模型
  - 模型ID: `anthropic.claude-sonnet-4-20250514-v1:0`
- **Claude Sonnet 4.5** - 最新增强版本
  - 模型ID: `anthropic.claude-sonnet-4-5-20250929-v1:0`

#### Amazon Nova 系列
- **Nova Micro** - 轻量级模型，低成本推理
  - 模型ID: `amazon.nova-micro-v1:0`
- **Nova Lite** - 轻型模型，性能和成本平衡
  - 模型ID: `amazon.nova-lite-v1:0`
- **Nova Pro** - 中等规模模型，多用途
  - 模型ID: `amazon.nova-pro-v1:0`
- **Nova Premier** - 高性能模型，复杂任务
  - 模型ID: `amazon.nova-premier-v1:0`

### 图片模式（IMAGE_MODELS）

#### Claude Vision 支持
- 所有上述 Claude 模型都支持 Vision（图片分析）
- 添加了最新的 Claude 3.5、3.7 和 4.x 系列

#### Amazon Nova 多模态支持
- **Nova Pro (Multimodal)** - 支持图片输入
  - 模型ID: `amazon.nova-pro-v1:0`
- **Nova Premier (Multimodal)** - 支持图片输入的高性能版本
  - 模型ID: `amazon.nova-premier-v1:0`

## 模型对比

### Claude 系列特性

| 模型 | 速度 | 推理能力 | 成本 | 适用场景 |
|------|------|--------|------|--------|
| Claude Haiku 4.5 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | 快速响应、简单任务 |
| Claude Sonnet 4 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 平衡性能和成本 |
| Claude Sonnet 4.5 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 复杂推理、代码生成 |

### Nova 系列特性

| 模型 | 速度 | 推理能力 | 成本 | 适用场景 |
|------|------|--------|------|--------|
| Nova Micro | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | 超轻量级应用 |
| Nova Lite | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | 轻型应用、成本敏感 |
| Nova Pro | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | 多用途、通用任务 |
| Nova Premier | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | 高性能、复杂任务 |

## 更新内容

### 1. 模型 ID 修正
- **Claude 3.5 Sonnet** 旧ID：`anthropic.claude-3-5-sonnet-20241022-v2:0`
  新ID：`anthropic.claude-3-5-sonnet-20240620-v1:0`
  原因：确保与 AWS Bedrock 批处理支持的模型一致

### 2. 模型组织结构
- 按照系列版本进行分组（Claude 3.x, 3.5, 3.7, 4.x）
- 添加了注释说明每个系列的特点
- 在图片模式中标注了 Nova 多模态支持

### 3. 向后兼容性
- 保留了所有现有模型
- 添加的新模型不会影响现有代码
- Claude 3.5 Sonnet V2 保持不变

## 使用建议

### 文本处理推荐
1. **快速响应场景** → Claude Haiku 4.5 / Nova Micro
2. **通用任务** → Claude Sonnet 4.5 / Nova Pro
3. **复杂推理** → Claude Sonnet 4.5 / Nova Premier
4. **成本优化** → Nova Micro / Nova Lite

### 图片处理推荐
1. **图片分析** → Claude 3.5+ 系列
2. **多模态任务** → Nova Pro/Premier (Multimodal)
3. **Vision 提取** → Claude Sonnet 4.5
4. **轻量级视觉** → Claude Haiku 4.5

## 区域支持

不同模型在不同 AWS 区域的支持情况不同。常用区域：
- **us-east-1** - 大多数模型支持
- **us-west-2** - 广泛支持
- **eu-west-1** - 欧洲用户推荐
- **ap-northeast-1** - 亚洲用户推荐

详见：https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference-supported.html

## 更新影响

### 受影响的文件
- ✅ `config.py` - 已更新

### 不需要修改的文件
- ✅ `ui_text.py` - 自动从 TEXT_MODELS 读取
- ✅ `ui_image.py` - 自动从 IMAGE_MODELS 读取
- ✅ `job_handlers.py` - 无需修改
- ✅ `batch_manager/` - 无需修改

### UI 影响
模型选择下拉框会自动显示所有新模型，无需额外配置。

## 版本信息

- **更新日期**: 2025-11-14
- **模型列表版本**: Bedrock Q4 2024 / Q1 2025
- **文本模型数量**: 14 个（从 5 个增加到 14 个）
- **图片模型数量**: 12 个（从 5 个增加到 12 个）

## 常见问题

### Q: 我应该选择哪个 Claude 模型？
A: 如果预算允许，推荐使用最新的 Claude Sonnet 4.5 或 Claude Haiku 4.5（快速场景）。它们提供了最好的性能和稳定性。

### Q: Nova 模型和 Claude 哪个更好？
A: 没有绝对的"好"或"坏"：
- **Claude** - 推理能力强，适合复杂任务
- **Nova** - 成本低、速度快，适合大规模、实时应用

### Q: 批处理支持所有这些模型吗？
A: 是的，这个列表中的所有模型都已获得 AWS Bedrock 批处理支持。

### Q: 我如何知道我的 region 支持某个模型？
A: 建议在 AWS Console 或查看官方文档确认您的 region 支持情况。

## 迁移说明

### 从旧版本升级
1. 更新 `config.py` 文件
2. 重启应用
3. 新模型会自动出现在下拉列表中

### 现有任务
已提交的任务不受影响，继续使用原有模型正常处理。

## 相关文档

- AWS Bedrock 支持的模型：https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html
- 批处理支持的模型：https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference-supported.html
- Claude 模型参数：https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-claude.html
- Amazon Nova 文档：https://aws.amazon.com/bedrock/amazon-nova/
