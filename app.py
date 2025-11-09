"""
AWS Bedrock 批量推理 Gradio Demo
支持文本批量处理功能
"""
import gradio as gr
import pandas as pd
from batch_manager import BatchInferenceManager
import time
from datetime import datetime
from typing import Optional, List
import json
import os

# 支持的模型列表
SUPPORTED_MODELS = {
    "Claude 3 Haiku": "anthropic.claude-3-haiku-20240307-v1:0",
    "Claude 3 Sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
    "Claude 3.5 Sonnet": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "Claude 3 Opus": "anthropic.claude-3-opus-20240229-v1:0"
}

# 状态文件路径
STATE_FILE = 'job_states.json'

# 全局变量存储当前任务
current_job_info = {
    'job_arn': None,
    'manager': None,
    'output_bucket': None,
    'output_prefix': None,
    'aws_region': None,
    'input_bucket': None,
    'input_prefix': None
}


def save_job_state(job_arn: str, job_info: dict):
    """保存任务状态到文件"""
    try:
        # 读取现有状态
        states = {}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                states = json.load(f)
        
        # 更新状态（不保存manager对象）
        states[job_arn] = {
            'job_arn': job_arn,
            'output_bucket': job_info.get('output_bucket'),
            'output_prefix': job_info.get('output_prefix'),
            'aws_region': job_info.get('aws_region'),
            'input_bucket': job_info.get('input_bucket'),
            'input_prefix': job_info.get('input_prefix'),
            'timestamp': datetime.now().isoformat()
        }
        
        # 保存到文件
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(states, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"保存状态失败: {e}")


def load_job_state(job_arn: str = None) -> dict:
    """加载任务状态"""
    try:
        if not os.path.exists(STATE_FILE):
            return None
            
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            states = json.load(f)
        
        if job_arn:
            return states.get(job_arn)
        else:
            # 返回最新的任务
            if states:
                latest = max(states.values(), key=lambda x: x.get('timestamp', ''))
                return latest
            return None
            
    except Exception as e:
        print(f"加载状态失败: {e}")
        return None


def get_all_job_states() -> list:
    """获取所有任务状态列表"""
    try:
        if not os.path.exists(STATE_FILE):
            return []
            
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            states = json.load(f)
        
        # 按时间倒序排序
        job_list = sorted(states.values(), key=lambda x: x.get('timestamp', ''), reverse=True)
        return job_list[:10]  # 只返回最近10个任务
        
    except Exception as e:
        print(f"获取任务列表失败: {e}")
        return []


def create_batch_manager(bedrock_region: str = 'us-east-1', s3_region: str = 'us-east-1') -> BatchInferenceManager:
    """创建批处理管理器"""
    return BatchInferenceManager(bedrock_region=bedrock_region, s3_region=s3_region)


def preview_files(input_bucket: str, input_prefix: str, aws_region: str) -> tuple:
    """预览S3输入文件"""
    try:
        if not input_bucket:
            return None, "❌ 请输入Bucket名称"
        
        manager = create_batch_manager(bedrock_region=aws_region, s3_region=aws_region)
        files = manager.list_input_files(input_bucket, input_prefix)
        
        if not files:
            return None, f"⚠️ 在 {input_bucket}/{input_prefix} 中未找到任何文件"
        
        # 转换为DataFrame用于显示
        df = pd.DataFrame(files)
        message = f"✅ 找到 {len(files)} 个文件"
        
        return df, message
        
    except Exception as e:
        return None, f"❌ 预览文件失败: {str(e)}"


def validate_configuration(
    input_bucket: str,
    output_bucket: str,
    role_arn: str,
    aws_region: str
) -> str:
    """验证配置"""
    try:
        if not all([input_bucket, output_bucket, role_arn]):
            return "❌ 请填写所有必填配置项"
        
        manager = create_batch_manager(bedrock_region=aws_region, s3_region=aws_region)
        result = manager.validate_permissions(role_arn, input_bucket, output_bucket)
        
        # 构建验证结果消息
        message_parts = ["### 权限验证结果\n"]
        message_parts.append(f"**AWS Region:** {aws_region}\n")
        
        # 显示检查通过的项
        if result['checks']:
            message_parts.append("#### ✅ 检查通过：")
            for check in result['checks']:
                message_parts.append(f"- {check}")
        
        # 显示错误
        if result['errors']:
            message_parts.append("\n#### ❌ 发现问题：")
            for error in result['errors']:
                message_parts.append(f"- {error}")
        
        if result['valid']:
            message_parts.append("\n### 🎉 配置验证通过，可以开始批处理！")
        else:
            message_parts.append("\n### ⚠️ 请修复上述问题后再提交任务")
        
        return "\n".join(message_parts)
        
    except Exception as e:
        return f"❌ 验证失败: {str(e)}"


def start_batch_job(
    use_jsonl: bool,
    input_bucket: str,
    input_prefix: str,
    jsonl_s3_uri: str,
    output_bucket: str = "",
    output_prefix: str = "",
    prompt: str = "",
    model_name: str = "",
    role_arn: str = "",
    aws_region: str = "us-east-1",
    progress=gr.Progress()
) -> tuple:
    """启动批处理任务（支持两种模式）"""
    # 初始化处理日志
    processing_log = []
    
    def log_callback(step: str, current: int, total: int, details: str):
        """进度回调函数"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        if step == 'scan':
            emoji = '🔍'
        elif step == 'process':
            emoji = '📄'
            if total > 0:
                progress_pct = (current / total * 0.6) + 0.3
                progress(progress_pct, desc=f"处理文件 {current}/{total}")
        elif step == 'generate':
            emoji = '📝'
            progress(0.9, desc="生成JSONL文件...")
        elif step == 'error':
            emoji = '❌'
        else:
            emoji = '⏳'
        
        log_entry = f"{emoji} [{timestamp}] {details}"
        processing_log.append(log_entry)
    
    try:
        # 基础验证
        if not all([output_bucket, model_name, role_arn]):
            return (
                "❌ 请填写所有必填字段",
                None,
                gr.update(visible=False),
                gr.update(visible=False),
                ""
            )
        
        model_id = SUPPORTED_MODELS.get(model_name)
        if not model_id:
            return (
                "❌ 无效的模型选择",
                None,
                gr.update(visible=False),
                gr.update(visible=False),
                ""
            )
        
        progress(0, desc="正在初始化...")
        log_callback('init', 0, 0, '正在初始化批处理管理器...')
        
        # 创建管理器
        manager = create_batch_manager(bedrock_region=aws_region, s3_region=aws_region)
        
        # 根据模式选择不同的处理逻辑
        if use_jsonl:
            # JSONL文件模式：直接使用已有的JSONL文件
            if not jsonl_s3_uri:
                return (
                    "❌ 请输入JSONL文件的S3 URI",
                    None,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    ""
                )
            
            log_callback('jsonl', 0, 1, f'使用已有JSONL文件: {jsonl_s3_uri}')
            progress(0.5, desc="正在提交批处理任务...")
            
            # 使用已有JSONL文件创建任务
            result = manager.create_batch_job_from_jsonl(
                jsonl_s3_uri=jsonl_s3_uri,
                output_bucket=output_bucket,
                output_prefix=output_prefix,
                model_id=model_id,
                role_arn=role_arn
            )
            
            log_callback('jsonl', 1, 1, '✅ 使用已有JSONL文件，跳过数据处理步骤')
        else:
            # 原始文件模式：读取文件并生成JSONL
            if not all([input_bucket, prompt]):
                return (
                    "❌ 原始文件模式需要填写输入Bucket和Prompt",
                    None,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    ""
                )
            
            # 创建批处理任务（带进度回调）
            result = manager.create_batch_job(
                input_bucket=input_bucket,
                input_prefix=input_prefix,
                output_bucket=output_bucket,
                output_prefix=output_prefix,
                model_id=model_id,
                role_arn=role_arn,
                prompt=prompt,
                progress_callback=log_callback
            )
        
        if not result['success']:
            return (
                f"❌ {result['message']}",
                None,
                gr.update(visible=False),
                gr.update(visible=False),
                "\n".join(processing_log)
            )
        
        # 保存任务信息到内存
        current_job_info['job_arn'] = result['job_arn']
        current_job_info['manager'] = manager
        current_job_info['output_bucket'] = output_bucket
        current_job_info['output_prefix'] = output_prefix
        current_job_info['aws_region'] = aws_region
        current_job_info['input_bucket'] = input_bucket
        current_job_info['input_prefix'] = input_prefix
        
        # 持久化保存任务状态到文件
        save_job_state(result['job_arn'], {
            'output_bucket': output_bucket,
            'output_prefix': output_prefix,
            'aws_region': aws_region,
            'input_bucket': input_bucket,
            'input_prefix': input_prefix
        })
        
        progress(1.0, desc="任务已提交...")
        log_callback('submit', 1, 1, f'✅ 批处理任务已成功提交到Bedrock')
        
        # 构建状态消息
        status_msg = f"""
### ✅ 批处理任务已提交

**任务信息：**
- 任务名称: {result['job_name']}
- 任务ARN: {result['job_arn']}
- 模型: {model_name}
- AWS Region: {aws_region}
- 状态: 已提交

{result['message']}

*任务正在后台执行，请点击"刷新状态"按钮查看最新进度*
"""
        
        return (
            status_msg,
            result['job_arn'],
            gr.update(visible=True),
            gr.update(visible=True),
            "\n".join(processing_log)
        )
        
    except Exception as e:
        log_callback('error', 0, 0, f'发生错误: {str(e)}')
        return (
            f"❌ 启动任务失败: {str(e)}",
            None,
            gr.update(visible=False),
            gr.update(visible=False),
            "\n".join(processing_log)
        )


def refresh_job_status(job_arn: str) -> tuple:
    """刷新任务状态"""
    try:
        if not job_arn or not current_job_info['manager']:
            return "⚠️ 没有正在运行的任务", None, gr.update(visible=False, interactive=False)
        
        manager = current_job_info['manager']
        status_info = manager.get_job_status(job_arn)
        
        status = status_info.get('status', 'Unknown')
        
        # 状态映射
        status_emoji = {
            'Submitted': '📝',
            'InProgress': '⏳',
            'Completed': '✅',
            'Failed': '❌',
            'Stopped': '🛑',
            'Error': '❌'
        }
        
        emoji = status_emoji.get(status, '❓')
        
        # 构建状态消息
        status_msg = f"""
### {emoji} 任务状态: {status}

**任务详情：**
- 任务ARN: {job_arn}
- 提交时间: {status_info.get('submit_time', 'N/A')}
- 最后更新: {status_info.get('last_modified', 'N/A')}
- 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        if status_info.get('message'):
            status_msg += f"\n**消息:** {status_info['message']}"
        
        # 按钮状态控制：任务完成时才可点击
        button_interactive = status == 'Completed'
        
        if status == 'Completed':
            status_msg += "\n\n### 🎉 任务已完成！\n请点击下方'获取结果'按钮查看处理结果。"
        elif status == 'Failed':
            status_msg += "\n\n### ❌ 任务失败\n请检查配置和权限设置。"
        elif status in ['Submitted', 'InProgress']:
            status_msg += "\n\n*任务正在处理中，请稍后再次刷新...*"
        
        return (
            status_msg,
            None if not button_interactive else "ready",
            gr.update(visible=True, interactive=button_interactive)
        )
        
    except Exception as e:
        return f"❌ 获取状态失败: {str(e)}", None, gr.update(visible=False, interactive=False)


def restore_job(job_arn: str) -> tuple:
    """恢复任务状态"""
    try:
        if not job_arn or not job_arn.strip():
            return (
                "❌ 请输入有效的Job ARN",
                None,
                gr.update(visible=False),
                gr.update(visible=False)
            )
        
        job_arn = job_arn.strip()
        
        # 从文件加载任务状态
        job_state = load_job_state(job_arn)
        
        if not job_state:
            return (
                f"❌ 未找到任务 {job_arn} 的状态信息",
                None,
                gr.update(visible=False),
                gr.update(visible=False)
            )
        
        # 恢复到全局变量
        aws_region = job_state.get('aws_region', 'us-east-1')
        current_job_info['job_arn'] = job_arn
        current_job_info['manager'] = create_batch_manager(bedrock_region=aws_region, s3_region=aws_region)
        current_job_info['output_bucket'] = job_state.get('output_bucket')
        current_job_info['output_prefix'] = job_state.get('output_prefix')
        current_job_info['aws_region'] = aws_region
        current_job_info['input_bucket'] = job_state.get('input_bucket')
        current_job_info['input_prefix'] = job_state.get('input_prefix')
        
        # 获取任务最新状态
        manager = current_job_info['manager']
        status_info = manager.get_job_status(job_arn)
        status = status_info.get('status', 'Unknown')
        
        # 状态映射
        status_emoji = {
            'Submitted': '📝',
            'InProgress': '⏳',
            'Completed': '✅',
            'Failed': '❌',
            'Stopped': '🛑',
            'Error': '❌'
        }
        
        emoji = status_emoji.get(status, '❓')
        
        # 构建状态消息
        status_msg = f"""
### {emoji} 任务已恢复 - 状态: {status}

**任务详情：**
- 任务ARN: {job_arn}
- AWS Region: {aws_region}
- 提交时间: {status_info.get('submit_time', 'N/A')}
- 最后更新: {status_info.get('last_modified', 'N/A')}
- 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        if status_info.get('message'):
            status_msg += f"\n**消息:** {status_info['message']}"
        
        # 按钮状态控制
        button_interactive = status == 'Completed'
        
        if status == 'Completed':
            status_msg += "\n\n### 🎉 任务已完成！\n请点击下方'获取结果'按钮查看处理结果。"
        elif status == 'Failed':
            status_msg += "\n\n### ❌ 任务失败\n请检查配置和权限设置。"
        elif status in ['Submitted', 'InProgress']:
            status_msg += "\n\n*任务正在处理中，请点击'刷新状态'按钮查看最新进度*"
        
        return (
            status_msg,
            job_arn,
            gr.update(visible=True),
            gr.update(visible=True, interactive=button_interactive)
        )
        
    except Exception as e:
        return (
            f"❌ 恢复任务失败: {str(e)}",
            None,
            gr.update(visible=False),
            gr.update(visible=False)
        )


def get_results(job_arn: str) -> tuple:
    """获取任务结果（预览+下载）"""
    try:
        if not job_arn or not current_job_info['manager']:
            return "⚠️ 没有可用的任务结果", None, ""
        
        manager = current_job_info['manager']
        output_bucket = current_job_info['output_bucket']
        output_prefix = current_job_info['output_prefix']
        
        # 获取结果预览和下载链接
        result_data = manager.get_results_preview_and_download(job_arn, output_bucket, output_prefix)
        
        stats = result_data['stats']
        preview = result_data['preview']
        download_url = result_data['download_url']
        file_name = result_data['file_name']
        
        # 转换预览数据为DataFrame（截取output_text前100字符）
        preview_data = []
        for item in preview:
            preview_data.append({
                'record_id': item['record_id'],
                'output_text': item['output_text'][:100] + '...' if len(item['output_text']) > 100 else item['output_text'],
                'input_tokens': item['input_tokens'],
                'output_tokens': item['output_tokens']
            })
        
        df = pd.DataFrame(preview_data)
        
        # 构建结果消息
        message = f"""
### ✅ 结果获取成功

#### 📊 统计信息
- **处理记录数**: {stats['total_records']:,}
- **总输入Token**: {stats['total_input_tokens']:,}
- **总输出Token**: {stats['total_output_tokens']:,}
- **总Token使用**: {stats['total_tokens']:,}

#### 📋 数据预览（前5行）
*下方表格显示前5条记录的预览*

---
💡 **提示**: 完整结果包含所有记录的详细信息，点击下方的下载按钮获取完整JSONL文件。
"""
        
        # 构建HTML下载链接
        download_html = f"""
        <div style="padding: 20px; background-color: #f0f8ff; border-radius: 10px; border: 2px solid #4CAF50;">
            <h3 style="margin-top: 0; color: #2c3e50;">📥 下载完整结果</h3>
            <p style="margin: 10px 0;"><strong>文件名:</strong> {file_name}</p>
            <p style="margin: 10px 0;"><strong>链接有效期:</strong> 1小时</p>
            <a href="{download_url}" 
               target="_blank" 
               style="display: inline-block; 
                      padding: 12px 24px; 
                      background-color: #4CAF50; 
                      color: white; 
                      text-decoration: none; 
                      border-radius: 5px; 
                      font-weight: bold;
                      margin-top: 10px;">
                🔽 点击下载 JSONL 文件
            </a>
            <p style="margin: 15px 0 0 0; font-size: 0.9em; color: #666;">
                💡 如果点击无反应，请右键选择"在新标签页中打开链接"
            </p>
        </div>
        """
        
        return message, df, download_html
        
    except Exception as e:
        return f"❌ 获取结果失败: {str(e)}", None, ""


# 创建Gradio界面
def create_interface():
    """创建Gradio界面"""
    
    with gr.Blocks(
        title="AWS Bedrock 批量推理 Demo",
        theme=gr.themes.Soft()
    ) as demo:
        
        # 标题
        gr.Markdown(
            """
            # 🚀 AWS Bedrock 批量推理 Demo
            ### 文本批处理展示平台
            
            从S3读取文件并进行批量推理
            """
        )
        
        # 状态存储
        job_arn_state = gr.State(None)
        results_ready_state = gr.State(None)
        
        with gr.Row():
            with gr.Column(scale=2):
                # 配置区域
                gr.Markdown("## 📝 配置信息")
                
                with gr.Group():
                    gr.Markdown("### AWS区域配置")
                    aws_region = gr.Textbox(
                        label="AWS Region *",
                        value="us-east-1",
                        placeholder="AWS区域，如: us-east-1, us-west-2",
                        info="⚠️ 重要：Bedrock和S3必须在同一个region"
                    )
                
                with gr.Group():
                    gr.Markdown("### 输入配置")
                    
                    use_existing_jsonl = gr.Checkbox(
                        label="使用已有的JSONL文件（跳过数据处理）",
                        value=False,
                        info="如果您已经准备好了批处理输入的JSONL文件，勾选此项"
                    )
                    
                    input_bucket = gr.Textbox(
                        label="输入Bucket名称 *",
                        value="general-demo-1",
                        placeholder="例如: my-bucket"
                    )
                    
                    # 两种模式的输入配置
                    with gr.Group() as raw_files_group:
                        gr.Markdown("#### 📁 原始文件模式")
                        s3_input_prefix = gr.Textbox(
                            label="原始文件S3路径前缀",
                            value="bluefocus-raw_data/textual",
                            placeholder="例如: input/data（系统会自动处理末尾的'/'）",
                            info="留空表示bucket根目录"
                        )
                    
                    with gr.Group(visible=False) as jsonl_file_group:
                        gr.Markdown("#### 📄 JSONL文件模式")
                        jsonl_file_s3_uri = gr.Textbox(
                            label="JSONL文件S3 URI *",
                            placeholder="例如: s3://my-bucket/input/batch-input.jsonl",
                            info="完整的S3 URI路径，包含bucket和文件名"
                        )
                    
                with gr.Group():
                    gr.Markdown("### 输出配置")
                    with gr.Row():
                        output_bucket = gr.Textbox(
                            label="输出Bucket名称 *",
                            value="general-demo-1",
                            placeholder="例如: my-bucket"
                        )
                        output_prefix = gr.Textbox(
                            label="输出路径前缀",
                            value="bluefocus-batch-input/bluefocus-batch-output",
                            placeholder="例如: output/results（系统会自动处理末尾的'/'）",
                            info="留空表示bucket根目录"
                        )
                
                with gr.Group():
                    gr.Markdown("### 处理配置")
                    prompt_input = gr.Textbox(
                        label="Prompt提示词 *",
                        placeholder="例如: 请将以下文本翻译成中文",
                        lines=5
                    )
                    
                    with gr.Row():
                        model_dropdown = gr.Dropdown(
                            choices=list(SUPPORTED_MODELS.keys()),
                            value="Claude 3 Haiku",
                            label="选择模型 *"
                        )
                        role_arn_input = gr.Textbox(
                            label="Role ARN *",
                            value="arn:aws:iam::813923830882:role/demo-role-for-bluefocus-to-do-rolepass",
                            placeholder="arn:aws:iam::123456789012:role/your-role"
                        )
                
                # 操作按钮
                with gr.Row():
                    preview_btn = gr.Button("🔍 预览文件", variant="secondary", visible=True)
                    validate_btn = gr.Button("✓ 验证权限", variant="secondary")
                    start_btn = gr.Button("▶️ 开始批处理", variant="primary", size="lg")
            
            with gr.Column(scale=3):
                # 预览与状态区域
                gr.Markdown("## 📋 预览与状态")
                
                with gr.Group():
                    preview_message = gr.Markdown("点击'预览文件'查看S3文件列表")
                    preview_output = gr.DataFrame(
                        label="S3文件列表"
                    )
                
                with gr.Group():
                    validation_output = gr.Markdown("点击'验证权限'检查配置")
                
                with gr.Group():
                    gr.Markdown("### 📋 处理日志")
                    processing_log_display = gr.Textbox(
                        label="实时处理日志",
                        lines=12,
                        max_lines=20,
                        interactive=False,
                        show_copy_button=True,
                        placeholder="开始批处理后，这里将显示详细的处理日志..."
                    )
                
                with gr.Group():
                    status_display = gr.Markdown("等待任务提交...")
                    
                    with gr.Row():
                        refresh_btn = gr.Button(
                            "🔄 刷新状态",
                            visible=False,
                            variant="secondary"
                        )
                        results_btn = gr.Button(
                            "📊 获取结果",
                            visible=False,
                            variant="primary"
                        )
                
                with gr.Group():
                    results_message = gr.Markdown()
                    download_link_html = gr.HTML(label="下载链接")
                    results_df = gr.DataFrame(
                        label="处理结果",
                        wrap=True
                    )
        
        # 使用说明
        with gr.Accordion("📖 使用说明", open=False):
            gr.Markdown("""
            ### 重要说明：
            
            **⚠️ Region配置要求：**
            - Bedrock批处理要求**Bedrock和S3必须在同一个AWS Region**
            - 请确保您的S3 Bucket与Bedrock服务在同一区域
            - 常用区域：us-east-1, us-west-2, ap-northeast-1等
            
            **输入文件准备：**
            - 请提前将待处理的文本文件上传到S3 bucket
            - 系统会从指定的S3路径读取所有文件进行批量处理
            
            **路径前缀说明：**
            - 前缀格式如 `input/data` 或 `input/data/`
            - 系统会自动处理末尾的 `/`，无需担心格式问题
            - 留空表示使用bucket根目录
            
            ### 使用步骤：
            
            1. **配置AWS Region**: 设置Bedrock和S3所在的region（必须相同）
            2. **配置bucket和路径**: 填写输入/输出bucket及前缀
            3. **预览文件**: 可选，查看S3中待处理的文件列表
            4. **输入Prompt**: 描述要执行的处理任务
            5. **选择模型和Role**: 选择合适的模型和IAM角色
            6. **验证权限**: 可选，确保配置正确
            7. **开始处理**: 提交批处理任务
            8. **监控和获取结果**: 刷新状态并获取结果
            """)
        
        # 事件绑定 - 切换输入模式
        def toggle_input_mode(use_jsonl):
            """切换输入模式显示"""
            if use_jsonl:
                return gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)
            else:
                return gr.update(visible=True), gr.update(visible=False), gr.update(visible=True)
        
        use_existing_jsonl.change(
            fn=toggle_input_mode,
            inputs=[use_existing_jsonl],
            outputs=[raw_files_group, jsonl_file_group, preview_btn]
        )
        
        # 事件绑定 - 预览文件
        preview_btn.click(
            fn=preview_files,
            inputs=[input_bucket, s3_input_prefix, aws_region],
            outputs=[preview_output, preview_message]
        )
        
        # 事件绑定 - 验证权限
        validate_btn.click(
            fn=validate_configuration,
            inputs=[input_bucket, output_bucket, role_arn_input, aws_region],
            outputs=[validation_output]
        )
        
        # 事件绑定 - 开始批处理
        start_btn.click(
            fn=start_batch_job,
            inputs=[
                use_existing_jsonl, input_bucket, s3_input_prefix, jsonl_file_s3_uri,
                output_bucket, output_prefix,
                prompt_input, model_dropdown, role_arn_input,
                aws_region
            ],
            outputs=[status_display, job_arn_state, refresh_btn, results_btn, processing_log_display]
        )
        
        # 事件绑定 - 刷新状态
        refresh_btn.click(
            fn=refresh_job_status,
            inputs=[job_arn_state],
            outputs=[status_display, results_ready_state, results_btn]
        )
        
        # 事件绑定 - 获取结果
        results_btn.click(
            fn=get_results,
            inputs=[job_arn_state],
            outputs=[results_message, download_link_html, results_df]
        )
    
    return demo


if __name__ == "__main__":
    demo = create_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
