# 🚀 快速开始指南

这是一个5分钟快速上手指南，帮助你快速运行AWS Bedrock批量推理Demo。

## 前提条件

确保你已经：
- ✅ 安装了Python 3.8+
- ✅ 配置了AWS凭证（AWS CLI或环境变量）
- ✅ 有可访问的S3 bucket
- ✅ 有Bedrock访问权限

## 快速启动（3步）

### 1️⃣ 安装依赖
```bash
pip install -r requirements.txt
```

### 2️⃣ 启动应用
```bash
# 方式1：使用启动脚本（推荐）
./run.sh

# 方式2：直接运行
python3 app.py
```

### 3️⃣ 访问界面
打开浏览器访问：**http://localhost:7860**

## 测试示例

### 示例1：文本翻译

**输入配置：**
- 输入Bucket: `my-bucket`
- 输入路径: `input/texts/`
- 输出Bucket: `my-bucket`
- 输出路径: `output/translations`

**Prompt提示词：**
```
请将以下英文文本翻译成中文，保持原文的格式和结构。
```

**模型选择：** Claude 3 Haiku

**Role ARN：** `arn:aws:iam::123456789012:role/bedrock-batch-role`

### 示例2：文本摘要

**Prompt提示词：**
```
请用100字以内总结以下文本的主要内容，要求简洁明了。
```

**模型选择：** Claude 3.5 Sonnet

### 示例3：情感分析

**Prompt提示词：**
```
请分析以下文本的情感倾向（正面/负面/中性），并给出评分（1-10分）。
```

**模型选择：** Claude 3 Sonnet

## 准备测试数据

在S3创建测试文件：

```bash
# 创建测试文本文件
echo "Hello, this is a test document." > test1.txt
echo "This is another example text file." > test2.txt

# 上传到S3
aws s3 cp test1.txt s3://your-bucket/input/
aws s3 cp test2.txt s3://your-bucket/input/
```

## 常见问题快速解决

### ❌ AWS凭证错误
```bash
# 配置AWS凭证
aws configure

# 或使用环境变量
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

### ❌ 权限不足
确保你的IAM用户/角色有以下权限：
- Bedrock：CreateModelInvocationJob, GetModelInvocationJob
- S3：GetObject, PutObject, ListBucket
- IAM：PassRole

### ❌ 找不到文件
- 检查bucket名称拼写
- 确认路径前缀是否正确
- 使用"预览文件"功能验证

### ❌ 任务失败
1. 点击"验证权限"检查配置
2. 确认Role ARN有正确的信任关系
3. 检查输入文件格式是否正确

## 下一步

- 📖 阅读完整文档：[README.md](README.md)
- 🔧 自定义配置参数
- 📊 查看处理结果和统计
- 🚀 在服务器上部署

## 需要帮助？

- 查看[README.md](README.md)了解详细信息
- 检查AWS Bedrock文档
- 查看应用日志排查问题

---

**提示**: 第一次运行建议使用少量文件（2-3个）进行测试，验证配置正确后再处理大批量数据。
