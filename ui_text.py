"""
文本批处理UI模块
"""
import gradio as gr
from config import TEXT_MODELS
from job_handlers import (
    preview_files, validate_configuration, start_batch_job,
    refresh_job_status, get_results, validate_text_single_inference
)


def create_text_batch_interface(job_arn_state, results_ready_state):
    """创建文本批处理界面"""
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
                    value="batch-demo-txt-101-items",
                    placeholder="例如: my-bucket"
                )
                
                # 两种模式的输入配置
                with gr.Group() as raw_files_group:
                    gr.Markdown("#### 📁 原始文件模式")
                    s3_input_prefix = gr.Textbox(
                        label="原始文件S3路径前缀",
                        value="",
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
                        value="batch-demo-txt-101-items",
                        placeholder="例如: my-bucket"
                    )
                    output_prefix = gr.Textbox(
                        label="输出路径前缀",
                        value="batch-output/",
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
                        choices=list(TEXT_MODELS.keys()),
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
                    preview_btn = gr.Button("🔍 预览文件", variant="secondary")
                    validate_btn = gr.Button("✓ 参数检查", variant="secondary")
                with gr.Row():
                    validate_inference_btn = gr.Button("🧪 单次推理验证", variant="secondary")
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
                validation_output = gr.Markdown("点击'参数检查'检查配置")
            
            with gr.Group():
                gr.Markdown("### 🧪 单次推理验证结果")
                inference_validation_output = gr.Markdown("点击'单次推理验证'进行验证")
            
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
                download_link_html = gr.HTML(label="文件位置")
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
    def validate_with_model(inp_bucket, out_bucket, role, region, model):
        """包装函数确保所有参数都被传递"""
        return validate_configuration(inp_bucket, out_bucket, role, region, model)
    
    validate_btn.click(
        fn=validate_with_model,
        inputs=[input_bucket, output_bucket, role_arn_input, aws_region, model_dropdown],
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
    
    # 事件绑定 - 单次推理验证
    validate_inference_btn.click(
        fn=validate_text_single_inference,
        inputs=[
            use_existing_jsonl, input_bucket, s3_input_prefix, jsonl_file_s3_uri,
            prompt_input, model_dropdown, aws_region
        ],
        outputs=[inference_validation_output]
    )
