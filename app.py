"""
AWS Bedrock 批量推理 Gradio Demo
支持文本批量处理功能 - 增强版
支持双region配置和本地文件上传
"""
import gradio as gr
import pandas as pd
from batch_manager import BatchInferenceManager
import time
from datetime import datetime
from typing import Optional, List

# 支持的模型列表
SUPPORTED_MODELS = {
    "Claude 3 Haiku": "anthropic.claude-3-haiku-20240307-v1:0",
    "Claude 3 Sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
    "Claude 3.5 Sonnet": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "Claude 3 Opus": "anthropic.claude-3-opus-20240229-v1:0"
}

# 全局变量存储当前任务
current_job_info = {
    'job_arn': None,
    'manager': None,
    'output_bucket': None,
    'output_prefix': None
}


def create_batch_manager(bedrock_region: str = 'us-east-1', s3_region: str = 'us-east-1') -> BatchInferenceManager:
    """创建批处理管理器"""
    return BatchInferenceManager(bedrock_region=bedrock_region, s3_region=s3_region)


def toggle_file_source(choice: str) -> tuple:
    """根据文件来源选择切换界面"""
    if choice == "本地文件上传":
        return (
            gr.update(visible=True),   # 本地文件上传组件可见
            gr.update(visible=False),  # S3前缀输入不可见
            gr.update(visible=False)   # 预览按钮不可见
        )
    else:  # S3现有文件
        return (
            gr.update(visible=False),  # 本地文件上传组件不可见
            gr.update(visible=True),   # S3前缀输入可见
            gr.update(visible=True)    # 预览按钮可见
        )


def preview_files(input_bucket: str, input_prefix: str, bedrock_region: str, s3_region: str) -> tuple:
    """预览S3输入文件"""
    try:
        if not input_bucket:
            return None, "❌ 请输入Bucket名称"
        
        manager = create_batch_manager(bedrock_region=bedrock_region, s3_region=s3_region)
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
    bedrock_region: str,
    s3_region: str
) -> str:
    """验证配置"""
    try:
        if not all([input_bucket, output_bucket, role_arn]):
            return "❌ 请填写所有必填配置项"
        
        manager = create_batch_manager(bedrock_region=bedrock_region, s3_region=s3_region)
        result = manager.validate_permissions(role_arn, input_bucket, output_bucket)
        
        # 构建验证结果消息
        message_parts = ["### 权限验证结果\n"]
        message_parts.append(f"**Bedrock Region:** {bedrock_region}")
        message_parts.append(f"**S3 Region:** {s3_region}\n")
        
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
    file_source: str,
    input_bucket: str,
    input_prefix: str,
    local_files: Optional[List] = None,
    output_bucket: str = "",
    output_prefix: str = "",
    prompt: str = "",
    model_name: str = "",
    role_arn: str = "",
    bedrock_region: str = "us-east-1",
    s3_region: str = "us-east-1",
    progress=gr.Progress()
) -> tuple:
    """启动批处理任务"""
    try:
        # 验证输入
        if not all([input_bucket, output_bucket, prompt, model_name, role_arn]):
            return (
                "❌ 请填写所有必填字段",
                None,
                gr.update(visible=False),
                gr.update(visible=False)
            )
        
        model_id = SUPPORTED_MODELS.get(model_name)
        if not model_id:
            return (
                "❌ 无效的模型选择",
                None,
                gr.update(visible=False),
                gr.update(visible=False)
            )
        
        progress(0, desc="正在初始化...")
        
        # 创建管理器
        manager = create_batch_manager(bedrock_region=bedrock_region, s3_region=s3_region)
        
        # 处理本地文件
        local_file_paths = None
        if file_source == "本地文件上传" and local_files:
            progress(0.1, desc="正在上传本地文件...")
            local_file_paths = [f.name for f in local_files]
        
        progress(0.3, desc="正在准备批处理数据...")
        
        # 创建批处理任务
        result = manager.create_batch_job(
            input_bucket=input_bucket,
            input_prefix=input_prefix if file_source == "S3现有文件" else "",
            output_bucket=output_bucket,
            output_prefix=output_prefix,
            model_id=model_id,
            role_arn=role_arn,
            prompt=prompt,
            local_files=local_file_paths
        )
        
        if not result['success']:
            return (
                f"❌ {result['message']}",
                None,
                gr.update(visible=False),
                gr.update(visible=False)
            )
        
        # 保存任务信息
        current_job_info['job_arn'] = result['job_arn']
        current_job_info['manager'] = manager
        current_job_info['output_bucket'] = output_bucket
        current_job_info['output_prefix'] = output_prefix
        
        progress(0.8, desc="任务已提交...")
        
        # 构建状态消息
        status_msg = f"""
### ✅ 批处理任务已提交

**任务信息：**
- 任务名称: {result['job_name']}
- 任务ARN: {result['job_arn']}
- 模型: {model_name}
- Bedrock Region: {bedrock_region}
- S3 Region: {s3_region}
- 状态: 已提交

{result['message']}

*任务正在后台执行，请点击"刷新状态"按钮查看最新进度*
"""
        
        return (
            status_msg,
            result['job_arn'],
            gr.update(visible=True),
            gr.update(visible=True)
        )
        
    except Exception as e:
        return (
            f"❌ 启动任务失败: {str(e)}",
            None,
            gr.update(visible=False),
            gr.update(visible=False)
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


def get_results(job_arn: str) -> tuple:
    """获取任务结果（预览+下载）"""
    try:
        if not job_arn or not current_job_info['manager']:
            return "⚠️ 没有可用的任务结果", None
        
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

#### 📥 下载完整结果
**文件名**: {file_name}  
**下载链接**: [点击下载完整JSONL文件]({download_url})  
*链接有效期: 1小时*

---
💡 **提示**: 完整结果包含所有记录的详细信息，建议下载后使用文本编辑器或专业工具查看。
"""
        
        return message, df
        
    except Exception as e:
        return f"❌ 获取结果失败: {str(e)}", None


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
            ### 文本批处理展示平台 - 增强版
            
            支持双Region配置和本地文件上传功能
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
                    with gr.Row():
                        bedrock_region = gr.Textbox(
                            label="Bedrock Region *",
                            value="us-east-1",
                            placeholder="模型调用区域，如: us-east-1"
                        )
                        s3_region = gr.Textbox(
                            label="S3 Region *",
                            value="us-east-1",
                            placeholder="Bucket所在区域，如: us-west-2"
                        )
                
                with gr.Group():
                    gr.Markdown("### 文件来源")
                    file_source = gr.Radio(
                        choices=["S3现有文件", "本地文件上传"],
                        value="S3现有文件",
                        label="选择文件来源"
                    )
                
                with gr.Group():
                    gr.Markdown("### 输入配置")
                    input_bucket = gr.Textbox(
                        label="输入Bucket名称 *",
                        placeholder="例如: my-bucket"
                    )
                    
                    # S3路径前缀（S3模式）
                    s3_input_prefix = gr.Textbox(
                        label="S3路径前缀（S3模式）",
                        placeholder="例如: input/data（系统会自动处理末尾的'/'）",
                        info="留空表示bucket根目录",
                        visible=True
                    )
                    
                    # 本地文件上传（本地模式）
                    local_files_upload = gr.File(
                        label="选择本地文件（本地模式）",
                        file_count="multiple",
                        file_types=[".txt"],
                        visible=False
                    )
                    
                with gr.Group():
                    gr.Markdown("### 输出配置")
                    with gr.Row():
                        output_bucket = gr.Textbox(
                            label="输出Bucket名称 *",
                            placeholder="例如: my-bucket"
                        )
                        output_prefix = gr.Textbox(
                            label="输出路径前缀",
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
                    preview_message = gr.Markdown("点击'预览文件'查看S3文件列表（仅S3模式）")
                    preview_output = gr.DataFrame(
                        label="S3文件列表"
                    )
                
                with gr.Group():
                    validation_output = gr.Markdown("点击'验证权限'检查配置")
                
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
                    results_df = gr.DataFrame(
                        label="处理结果",
                        wrap=True
                    )
        
        # 使用说明
        with gr.Accordion("📖 使用说明", open=False):
            gr.Markdown("""
            ### 新功能说明：
            
            **双Region支持：**
            - **Bedrock Region**: 模型调用使用的区域
            - **S3 Region**: Bucket所在的区域
            - 可以根据实际需求配置不同区域
            
            **文件来源模式：**
            1. **S3现有文件**: 从S3 bucket读取已有文件
            2. **本地文件上传**: 上传本地文件到S3再处理（会自动保存到raw_data目录）
            
            **路径前缀说明：**
            - 前缀格式如 `input/data` 或 `input/data/`
            - 系统会自动处理末尾的 `/`，无需担心格式问题
            - 留空表示使用bucket根目录
            
            ### 使用步骤：
            
            1. **配置区域**: 设置Bedrock和S3的region
            2. **选择文件来源**: S3现有文件或本地上传
            3. **配置bucket和路径**: 填写输入/输出bucket及前缀
            4. **输入Prompt**: 描述要执行的处理任务
            5. **选择模型和Role**: 选择合适的模型和IAM角色
            6. **验证权限**: 确保配置正确
            7. **开始处理**: 提交批处理任务
            8. **监控和获取结果**: 刷新状态并获取结果
            """)
        
        # 事件绑定 - 文件来源切换
        file_source.change(
            fn=toggle_file_source,
            inputs=[file_source],
            outputs=[local_files_upload, s3_input_prefix, preview_btn]
        )
        
        # 事件绑定 - 预览文件
        preview_btn.click(
            fn=preview_files,
            inputs=[input_bucket, s3_input_prefix, bedrock_region, s3_region],
            outputs=[preview_output, preview_message]
        )
        
        # 事件绑定 - 验证权限
        validate_btn.click(
            fn=validate_configuration,
            inputs=[input_bucket, output_bucket, role_arn_input, bedrock_region, s3_region],
            outputs=[validation_output]
        )
        
        # 事件绑定 - 开始批处理
        start_btn.click(
            fn=start_batch_job,
            inputs=[
                file_source, input_bucket, s3_input_prefix,
                local_files_upload, output_bucket, output_prefix,
                prompt_input, model_dropdown, role_arn_input,
                bedrock_region, s3_region
            ],
            outputs=[status_display, job_arn_state, refresh_btn, results_btn]
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
            outputs=[results_message, results_df]
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
