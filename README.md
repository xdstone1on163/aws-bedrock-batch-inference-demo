# AWS Bedrock 批量推理 Demo

这是一个基于Gradio的AWS Bedrock批量推理演示应用，用于展示如何使用Bedrock的批量推理功能处理大量文本数据。

## 功能特性

- 🚀 **批量文本处理**：一次性处理多个文本文件
- 📊 **实时状态监控**：实时查看任务执行状态
- 🔍 **文件预览**：预览输入bucket中的文件
- ✅ **权限验证**：提交前验证AWS权限配置
- 📈 **结果展示**：以表格形式展示处理结果和统计信息
- 🎨 **友好界面**：直观的Web界面，易于操作

## 支持的模型

- Claude 3 Haiku
- Claude 3 Sonnet
- Claude 3.5 Sonnet
- Claude 3 Opus

## 系统要求

- Python 3.8+
- AWS账户和配置的凭证
- 对S3 bucket的读写权限
- 对Bedrock服务的访问权限

## 安装步骤

### 1. 克隆或下载项目

```bash
cd bedrock_batch_inference_demo
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置AWS凭证

#### 方式1：使用AWS CLI（推荐）

```bash
aws configure
```

输入你的：
- AWS Access Key ID
- AWS Secret Access Key
- Default region name (例如: us-east-1)
- Default output format (json)

#### 方式2：使用环境变量

```bash
export AWS_ACCESS_KEY_ID=your_access_key_id
export AWS_SECRET_ACCESS_KEY=your_secret_access_key
export AWS_DEFAULT_REGION=us-east-1
```

## 权限配置

### 应用程序所需权限

运行此应用的用户/角色需要以下权限：

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

用户在界面中提供的Role需要以下权限：

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

## 使用方法

### 1. 准备输入数据

在S3 bucket中准备要处理的文本文件：

```
s3://your-bucket/input/
  ├── file1.txt
  ├── file2.txt
  └── file3.txt
```

### 2. 启动应用

```bash
python app.py
```

应用将在 http://localhost:7860 启动

### 3. 使用界面

1. **配置信息**
   - 输入AWS区域（默认us-east-1）
   - 填写输入bucket名称和路径前缀
   - 填写输出bucket名称和路径前缀
   - 输入处理提示词（例如："请将以下文本翻译成中文"）
   - 选择要使用的模型
   - 提供IAM Role ARN

2. **预览和验证**
   - 点击"预览输入文件"查看输入文件列表
   - 点击"验证权限"检查配置是否正确

3. **开始处理**
   - 点击"开始批处理"提交任务
   - 任务提交后，使用"刷新状态"按钮查看进度

4. **获取结果**
   - 任务完成后，点击"获取结果"查看处理结果
   - 结果将显示在表格中，包含输入/输出token统计

## 项目结构

```
bedrock_batch_inference_demo/
├── app.py                              # Gradio主应用
├── batch_manager.py                    # 批处理管理类
├── requirements.txt                    # Python依赖
├── README.md                           # 项目文档
├── batch-inference-demo-*.ipynb        # 示例notebook（参考）
└── bedrock_batch_inference_demo.code-workspace  # VSCode工作区
```

## 核心组件说明

### app.py
主应用文件，包含：
- Gradio界面定义
- 事件处理函数
- 用户交互逻辑

### batch_manager.py
批处理管理器，提供：
- `list_input_files()`: 列出输入文件
- `prepare_batch_data()`: 准备批处理数据
- `create_batch_job()`: 创建批处理任务
- `get_job_status()`: 获取任务状态
- `get_job_results()`: 获取处理结果
- `validate_permissions()`: 验证权限配置

## 常见问题

### Q: 如何在服务器上运行？

修改 `app.py` 中的启动参数：
```python
demo.launch(
    server_name="0.0.0.0",  # 允许外部访问
    server_port=7860,
    share=False  # 或设置为True以获取公共链接
)
```

### Q: 任务需要多长时间？

批处理任务的执行时间取决于：
- 输入文件数量和大小
- 选择的模型
- 当前系统负载

通常从几分钟到几小时不等。

### Q: 如何处理大文件？

对于非常大的文本文件，建议：
1. 将文件分割成较小的块
2. 调整`max_tokens`参数
3. 使用更大容量的模型（如Claude 3 Opus）

### Q: 支持哪些文本格式？

目前支持UTF-8编码的纯文本文件（.txt）。

### Q: 如何查看详细日志？

可以在代码中添加日志记录：
```python
import logging
logging.basicConfig(level=logging.INFO)
```

## 成本估算

批量推理的成本取决于：
- 使用的模型
- 处理的token数量
- AWS区域

请参考[AWS Bedrock定价](https://aws.amazon.com/bedrock/pricing/)了解详细信息。

## 故障排除

### 权限错误
- 确保AWS凭证配置正确
- 检查IAM角色权限策略
- 验证S3 bucket访问权限

### 任务失败
- 检查输入文件格式
- 验证Role ARN配置
- 查看任务错误消息

### 无法访问S3
- 确认bucket名称拼写正确
- 检查bucket所在区域
- 验证bucket策略

## 贡献

欢迎提交问题和改进建议！

## 许可证

本项目仅供演示和学习使用。

## 联系方式

如有问题，请创建Issue或联系项目维护者。

## 致谢

本项目基于以下技术构建：
- AWS Bedrock
- Gradio
- boto3

---

**注意**: 使用此应用产生的AWS费用由用户承担。请确保了解相关服务的定价信息。
