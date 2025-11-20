# AWS Bedrock 批量推理 Demo

这是一个基于Gradio的AWS Bedrock批量推理演示应用，支持**文本**、**图片**和**视频**三种模式的批量处理。

## ✨ 功能特性

### 🎯 三种批处理模式
- **📝 文本批处理**：批量处理文本文件，支持翻译、总结、分析等任务
- **🖼️ 图片批处理**：批量分析图片内容，使用Claude Vision模型
- **🎬 视频批处理**：批量理解视频内容，使用Amazon Nova模型

### 💫 核心功能
- 🚀 **批量处理**：一次性处理大量文件（支持100+文件）
- 📊 **实时监控**：实时查看任务执行状态和进度
- 🔍 **文件预览**：预览S3中的输入文件列表
- ✅ **参数检查**：提交前验证配置参数
- 📈 **结果展示**：以表格形式展示处理结果
- 🎨 **友好界面**：直观的Web界面，三个独立Tab页

### 🛠️ 技术特性
- **模块化架构**：清晰的代码结构，易于维护和扩展
- **流式处理**：避免内存溢出，支持大文件处理
- **完整日志**：详细的处理日志，便于调试和监控
- **错误处理**：健壮的错误处理机制，单个文件失败不影响其他文件
- **S3分页支持**：正确处理大量文件，避免遗漏

## 📦 支持的模型

### 文本模型
- Claude 3 Haiku
- Claude 3 Sonnet  
- Claude 3.5 Sonnet (v1 & v2)
- Claude 3 Opus

### 图片模型（Vision）
- Claude 3 Haiku
- Claude 3 Sonnet
- Claude 3.5 Sonnet (v1 & v2)
- Claude 3 Opus

### 视频模型
- Amazon Nova Lite
- Amazon Nova Pro

## 🔧 系统要求

- Python 3.8+
- AWS账户和配置的凭证
- 对S3 bucket的读写权限
- 对Bedrock服务的访问权限
- ⚠️ **重要**：Bedrock和S3必须在同一个AWS Region

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置AWS凭证

使用AWS CLI配置：

```bash
aws configure
```

或使用环境变量：

```bash
export AWS_ACCESS_KEY_ID=your_access_key_id
export AWS_SECRET_ACCESS_KEY=your_secret_access_key
export AWS_DEFAULT_REGION=us-east-1
```

### 3. 启动应用

```bash
python app.py
```

应用将在 http://localhost:7860 启动

## 📖 使用指南

### 文本批处理

1. **准备数据**：将.txt文件上传到S3
   ```
   s3://your-bucket/input/
     ├── file1.txt
     ├── file2.txt
     └── file3.txt
   ```

2. **配置参数**：
   - AWS Region（建议us-east-1）
   - 输入/输出bucket和路径
   - Prompt提示词
   - 选择模型和Role ARN

3. **开始处理**：
   - 可选：预览文件、检查参数
   - 点击"开始批处理"
   - 使用"刷新状态"监控进度
   - 任务完成后"获取结果"

### 图片批处理

1. **准备数据**：将图片文件上传到S3
   ```
   s3://your-bucket/input/pictures/
     ├── image1.jpg
     ├── image2.png
     └── image3.jpg
   ```

2. **配置参数**：
   - AWS Region（建议us-west-2）
   - 输入/输出bucket和路径
   - System Prompt（可选）和User Prompt
   - 选择Vision模型和Role ARN

3. **注意事项**：
   - 支持格式：JPG, JPEG, PNG, GIF, BMP, WEBP
   - 单个图片建议不超过20MB
   - Base64编码后不超过25MB限制

### 视频批处理

1. **准备数据**：将视频文件上传到S3
   ```
   s3://your-bucket/videos/
     ├── video1.mp4
     ├── video2.mov
     └── video3.mp4
   ```

2. **配置参数**：
   - AWS Region（建议us-west-2）
   - 输入/输出bucket和路径
   - System Prompt（可选）和User Prompt
   - 选择Nova模型和Role ARN

3. **注意事项**：
   - 支持格式：MP4, MOV, AVI, MKV, WEBM, FLV
   - 单个视频建议不超过20MB
   - 建议使用压缩视频以提高处理效率

## 📁 项目结构

```
bedrock-batch-inference-demo/
├── app.py                          # Gradio主应用
├── config.py                       # 模型配置
├── state_manager.py                # 状态管理
├── job_handlers.py                 # 任务处理函数
├── ui_text.py                      # 文本批处理UI
├── ui_image.py                     # 图片批处理UI
├── ui_video.py                     # 视频批处理UI
├── batch_manager/                  # 核心模块
│   ├── __init__.py
│   ├── core.py                     # 核心协调器
│   ├── s3_manager.py               # S3操作管理
│   ├── text_processor.py           # 文本处理
│   ├── image_processor.py          # 图片处理
│   ├── video_processor.py          # 视频处理
│   ├── job_manager.py              # 任务管理
│   └── validator.py                # 权限验证
├── requirements.txt                # Python依赖
└── README.md                       # 项目文档
```

## 🔑 权限配置

### 应用程序所需权限

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:CreateModelInvocationJob",
                "bedrock:GetModelInvocationJob",
                "bedrock:ListModelInvocationJobs"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-input-bucket/*",
                "arn:aws:s3:::your-input-bucket",
                "arn:aws:s3:::your-output-bucket/*",
                "arn:aws:s3:::your-output-bucket"
            ]
        },
        {
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "arn:aws:iam::*:role/*bedrock*"
        }
    ]
}
```

### Batch Inference Role ARN所需权限

**权限策略：**
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel"
            ],
            "Resource": "arn:aws:bedrock:*::foundation-model/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": "arn:aws:s3:::your-input-bucket/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject"
            ],
            "Resource": "arn:aws:s3:::your-output-bucket/*"
        }
    ]
}
```

**信任关系：**
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "bedrock.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
```

## 🎨 核心组件说明

### Core Module (batch_manager/)

#### core.py
批量推理核心协调器，整合所有功能模块

#### s3_manager.py
S3操作管理器：
- 支持分页列表（正确处理100+文件）
- 文件上传下载
- 路径规范化

#### text_processor.py
文本批处理器：
- 只处理.txt文件
- 生成JSONL格式的批处理输入
- 详细的处理日志

#### image_processor.py
图片批处理器：
- 支持多种图片格式
- Base64编码处理
- 大小检查（20MB限制）
- 流式写入避免内存溢出

#### video_processor.py
视频批处理器：
- 支持多种视频格式
- Nova原生API格式
- 大小检查和警告

#### job_manager.py
任务管理器：
- 创建和监控批处理任务
- **流式逐行读取结果**（避免JSON截断）
- 格式验证（区分输入/输出文件）
- 详细的错误诊断

#### validator.py
权限验证器：
- 基础参数格式检查
- 友好的错误提示

## 🆕 最新改进

### v2.0 更新（2024-11）

1. **✅ S3分页支持**
   - 正确处理100+文件
   - 详细的扫描日志

2. **✅ 错误处理增强**
   - 单个文件失败不影响其他文件
   - 详细记录跳过的文件及原因
   - Payload大小检查（20MB限制）

3. **✅ 结果获取优化**
   - 流式逐行读取，避免JSON截断
   - 格式验证，正确识别输出文件
   - 增强的错误诊断

4. **✅ UI改进**
   - 三个独立Tab页（文本/图片/视频）
   - 实时处理日志显示
   - 清晰的按钮命名（参数检查）

5. **✅ 文件过滤**
   - 文本批处理只处理.txt文件
   - 图片/视频批处理自动识别格式

## 💡 使用技巧

### 处理速度优化

- **网络是瓶颈**：处理速度主要取决于从S3下载文件的速度
- **并行处理**：当前是串行处理，可以考虑并行（需要代码修改）
- **文件压缩**：压缩图片和视频可以显著提高处理速度

### 成本优化

- 选择合适的模型（Haiku最便宜，Opus最强大）
- 控制max_tokens参数
- 批量处理比单次调用更经济

### 调试技巧

- 查看后端日志（运行app.py的终端）
- 使用"预览文件"功能检查输入
- 使用"参数检查"验证配置
- 先用小批量测试（2-5个文件）

## ❓ 常见问题

### Q: Region必须相同吗？
**A**: 是的，Bedrock批处理要求Bedrock服务和S3 bucket在同一个region。

### Q: 为什么只显示98个文件而不是101个？
**A**: 检查后端日志，查看哪些文件被跳过以及原因（可能是大小限制、格式问题等）。

### Q: 结果预览显示空白怎么办？
**A**: 
- 检查任务是否真的完成（状态为Completed）
- 查看后端日志中的详细错误信息
- 使用AWS CLI直接访问S3结果文件验证

### Q: 如何处理大文件？
**A**:
- 图片/视频：压缩文件到20MB以下
- 文本：分割成较小的文件
- 考虑调整处理策略

### Q: 支持其他文件格式吗？
**A**: 
- 文本：目前只支持.txt文件
- 图片：JPG, JPEG, PNG, GIF, BMP, WEBP
- 视频：MP4, MOV, AVI, MKV, WEBM, FLV

### Q: 如何在服务器上运行？
**A**: 修改 `app.py` 中的启动参数：
```python
demo.launch(
    server_name="0.0.0.0",
    server_port=7860,
    share=False
)
```

## 📊 性能参考

### 处理速度
- 文本（1KB）：约0.5秒/文件（主要是网络时间）
- 图片（1MB）：约2-3秒/文件
- 视频（5MB）：约5-10秒/文件

实际速度取决于：
- 网络带宽
- S3区域
- 文件大小

### 成本估算
请参考[AWS Bedrock定价](https://aws.amazon.com/bedrock/pricing/)

## 🐛 故障排除

### 权限错误
- ✅ 确保AWS凭证配置正确
- ✅ 检查IAM角色权限策略
- ✅ 验证S3 bucket访问权限
- ✅ 确认Role ARN格式正确

### 任务失败
- ✅ 检查输入文件格式
- ✅ 验证Role ARN配置
- ✅ 确认Region一致
- ✅ 查看详细错误日志

### 文件读取问题
- ✅ 确认文件路径前缀正确
- ✅ 检查文件是否真的存在
- ✅ 验证文件大小是否超限
- ✅ 查看后端日志中的跳过信息

### 结果解析失败
- ✅ 确认任务状态为Completed
- ✅ 检查是否读取了正确的输出文件
- ✅ 查看详细的流式读取日志
- ✅ 尝试使用AWS CLI手动查看S3文件

## 🤝 贡献

欢迎提交问题和改进建议！

## 📄 许可证

本项目仅供演示和学习使用。

## 🙏 致谢

本项目基于以下技术构建：
- AWS Bedrock
- Amazon Bedrock Batch Inference
- Gradio
- boto3

---

**⚠️ 注意**: 使用此应用产生的AWS费用由用户承担。请确保了解相关服务的定价信息。

**📮 联系**: 如有问题，请创建Issue或联系项目维护者。
