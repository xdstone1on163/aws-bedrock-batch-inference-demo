#!/bin/bash

# AWS Bedrock 批量推理 Demo 启动脚本

echo "================================"
echo "AWS Bedrock 批量推理 Demo"
echo "================================"
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到Python3，请先安装Python 3.8或更高版本"
    exit 1
fi

echo "✓ Python版本:"
python3 --version
echo ""

# 检查是否安装了依赖
echo "检查依赖包..."
if ! python3 -c "import gradio" 2>/dev/null; then
    echo "⚠️  未找到必要的依赖包，正在安装..."
    pip install -r requirements.txt
else
    echo "✓ 依赖包已安装"
fi

echo ""

# 检查AWS凭证
echo "检查AWS凭证配置..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "⚠️  警告: AWS凭证未配置或无效"
    echo "请运行 'aws configure' 配置您的凭证"
    echo ""
    echo "或设置环境变量:"
    echo "  export AWS_ACCESS_KEY_ID=your_key"
    echo "  export AWS_SECRET_ACCESS_KEY=your_secret"
    echo "  export AWS_DEFAULT_REGION=us-east-1"
    echo ""
else
    echo "✓ AWS凭证配置正常"
    aws sts get-caller-identity
fi

echo ""
echo "================================"
echo "启动Gradio应用..."
echo "================================"
echo ""
echo "应用将在以下地址启动:"
echo "  本地: http://localhost:7860"
echo "  网络: http://0.0.0.0:7860"
echo ""
echo "按 Ctrl+C 停止应用"
echo ""

# 启动应用
python3 app.py
