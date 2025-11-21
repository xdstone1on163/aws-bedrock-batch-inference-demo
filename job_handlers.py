"""
任务处理模块
处理批量推理任务的启动、状态查询、结果获取等
"""
import gradio as gr
import pandas as pd
from datetime import datetime
from config import TEXT_MODELS, IMAGE_MODELS, VIDEO_MODELS, current_job_info
from state_manager import save_job_state, load_job_state, create_batch_manager


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
    aws_region: str,
    model_name: str = None
) -> str:
    """验证配置"""
    try:
        if not all([input_bucket, output_bucket, role_arn]):
            return "❌ 请填写所有必填配置项"
        
        # 获取model_id（如果提供了model_name）
        model_id = None
        if model_name:
            # 尝试从不同的模型字典中获取model_id
            model_id = (TEXT_MODELS.get(model_name) or 
                       IMAGE_MODELS.get(model_name) or 
                       VIDEO_MODELS.get(model_name))
        
        manager = create_batch_manager(bedrock_region=aws_region, s3_region=aws_region)
        result = manager.validate_permissions(role_arn, input_bucket, output_bucket, model_id)
        
        # 构建验证结果消息
        message_parts = ["### 权限验证结果\n"]
        message_parts.append(f"**AWS Region:** {aws_region}\n")
        if model_id:
            message_parts.append(f"**模型ID:** {model_id}\n")
        
        # 显示检查通过的项
        if result['checks']:
            message_parts.append("#### ✅ 检查通过：")
            for check in result['checks']:
                message_parts.append(f"- {check}")
        
        # 显示警告
        if result.get('warnings'):
            message_parts.append("\n#### ⚠️ 警告：")
            for warning in result['warnings']:
                message_parts.append(f"- {warning}")
        
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
    """启动文本批处理任务（支持两种模式）"""
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
        
        model_id = TEXT_MODELS.get(model_name)
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
        current_job_info['job_type'] = 'text'  # 标记任务类型
        
        # 持久化保存任务状态到文件
        save_job_state(result['job_arn'], {
            'output_bucket': output_bucket,
            'output_prefix': output_prefix,
            'aws_region': aws_region,
            'input_bucket': input_bucket,
            'input_prefix': input_prefix,
            'job_type': 'text'
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


def start_image_batch_job(
    use_jsonl: bool,
    input_bucket: str,
    input_prefix: str,
    jsonl_s3_uri: str,
    output_bucket: str,
    output_prefix: str,
    model_name: str,
    role_arn: str,
    system_prompt: str,
    user_prompt: str,
    aws_region: str = "us-east-1",
    progress=gr.Progress()
) -> tuple:
    """启动图片批处理任务（支持两种模式）"""
    # 初始化处理日志
    processing_log = []
    
    def log_callback(step: str, current: int, total: int, details: str):
        """进度回调函数"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        if step == 'scan':
            emoji = '🔍'
        elif step == 'process':
            emoji = '🖼️'
            if total > 0:
                progress_pct = (current / total * 0.6) + 0.3
                progress(progress_pct, desc=f"处理图片 {current}/{total}")
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
        
        # 模式特定验证
        if use_jsonl:
            if not jsonl_s3_uri:
                return (
                    "❌ JSONL模式需要填写JSONL文件S3 URI",
                    None,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    ""
                )
        else:
            if not all([input_bucket, user_prompt]):
                return (
                    "❌ 原始图片模式需要填写输入Bucket和User Prompt",
                    None,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    ""
                )
        
        model_id = IMAGE_MODELS.get(model_name)
        if not model_id:
            return (
                "❌ 无效的模型选择",
                None,
                gr.update(visible=False),
                gr.update(visible=False),
                ""
            )
        
        progress(0, desc="正在初始化...")
        log_callback('init', 0, 0, '正在初始化图片批处理管理器...')
        
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
            
            log_callback('jsonl', 1, 1, '✅ 使用已有JSONL文件，跳过图片处理步骤')
        else:
            # 原始图片模式：读取图片并生成JSONL
            if not user_prompt:
                return (
                    "❌ 原始图片模式需要填写User Prompt",
                    None,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    ""
                )
            
            # 创建图片批处理任务（带进度回调）
            result = manager.create_image_batch_job(
                input_bucket=input_bucket,
                input_prefix=input_prefix,
                output_bucket=output_bucket,
                output_prefix=output_prefix,
                model_id=model_id,
                role_arn=role_arn,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
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
        current_job_info['job_type'] = 'image'  # 标记任务类型
        
        # 持久化保存任务状态到文件
        save_job_state(result['job_arn'], {
            'output_bucket': output_bucket,
            'output_prefix': output_prefix,
            'aws_region': aws_region,
            'input_bucket': input_bucket,
            'input_prefix': input_prefix,
            'job_type': 'image'
        })
        
        progress(1.0, desc="任务已提交...")
        log_callback('submit', 1, 1, f'✅ 图片批处理任务已成功提交到Bedrock')
        
        # 构建状态消息
        status_msg = f"""
### ✅ 图片批处理任务已提交

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
            f"❌ 启动图片批处理任务失败: {str(e)}",
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


def get_results(job_arn: str) -> tuple:
    """获取任务结果（预览+文件位置）"""
    try:
        if not job_arn or not current_job_info['manager']:
            return "⚠️ 没有可用的任务结果", "", None
        
        manager = current_job_info['manager']
        output_bucket = current_job_info['output_bucket']
        output_prefix = current_job_info['output_prefix']
        job_type = current_job_info.get('job_type', 'text')  # 默认为文本类型
        
        # 根据任务类型设置预览行数：视频1行，文本/图片3行
        max_preview_lines = 1 if job_type == 'video' else 3
        
        # 获取结果预览和文件位置（不生成下载链接）
        result_data = manager.get_results_preview_only(job_arn, output_bucket, output_prefix, max_preview_lines)
        
        preview = result_data['preview']
        s3_uri = result_data['s3_uri']
        file_name = result_data['file_name']
        bucket = result_data['bucket']
        key = result_data['key']
        parse_warning = result_data.get('parse_warning', '')
        manifest = result_data.get('manifest')
        manifest_s3_uri = result_data.get('manifest_s3_uri')
        
        # 转换预览数据为DataFrame（截取output_text前200字符）
        preview_data = []
        for item in preview:
            preview_data.append({
                'record_id': item['record_id'],
                'output_text': item['output_text'][:200] + '...' if len(item['output_text']) > 200 else item['output_text'],
                'stop_reason': item['stop_reason']
            })
        
        df = pd.DataFrame(preview_data) if preview_data else None
        
        # 构建结果消息
        if parse_warning:
            message = f"""
### ⚠️ 结果文件已找到，但预览数据解析失败

#### 📂 结果文件位置
- **S3 URI**: `{s3_uri}`
- **Bucket**: {bucket}
- **Key**: {key}
- **文件名**: {file_name}

#### ⚠️ 解析警告
{parse_warning}

---
💡 **提示**: 请直接使用AWS CLI或AWS Console访问完整的JSONL文件查看结果内容。
"""
        else:
            message = f"""
### ✅ 结果获取成功

#### 📂 结果文件位置
- **S3 URI**: `{s3_uri}`
- **Bucket**: {bucket}
- **Key**: {key}
- **文件名**: {file_name}
"""
            
            # 添加manifest信息（如果存在）
            if manifest:
                message += f"""
#### 📊 任务统计信息 (Manifest)
- **总记录数**: {manifest.get('totalRecordCount', 'N/A')}
- **已处理记录数**: {manifest.get('processedRecordCount', 'N/A')}
- **成功记录数**: {manifest.get('successRecordCount', 'N/A')}
- **失败记录数**: {manifest.get('errorRecordCount', 'N/A')}
- **输入Token数**: {manifest.get('inputTokenCount', 'N/A')}
- **输出Token数**: {manifest.get('outputTokenCount', 'N/A')}
- **Manifest文件**: `{manifest_s3_uri}`
"""
            
            message += """
#### 📋 数据预览（前几行）
*下方表格显示部分记录的预览*

---
💡 **提示**: 完整结果保存在上述S3位置，您可以使用AWS CLI或AWS Console访问完整的JSONL文件。
"""
        
        # 构建文件位置信息HTML（替代下载链接）
        location_html = f"""
        <div style="padding: 20px; background-color: #f0f8ff; border-radius: 10px; border: 2px solid #4CAF50;">
            <h3 style="margin-top: 0; color: #2c3e50;">📂 结果文件位置</h3>
            <div style="background-color: #ffffff; padding: 15px; border-radius: 5px; margin: 10px 0; font-family: monospace;">
                <p style="margin: 5px 0;"><strong>S3 URI:</strong></p>
                <p style="margin: 5px 0; color: #0066cc; word-break: break-all;">{s3_uri}</p>
            </div>
            <div style="margin-top: 15px;">
                <p style="margin: 5px 0; font-size: 0.9em;"><strong>访问方式:</strong></p>
                <ul style="margin: 5px 0; padding-left: 20px; font-size: 0.9em;">
                    <li>使用AWS CLI: <code style="background-color: #f5f5f5; padding: 2px 5px; border-radius: 3px;">aws s3 cp {s3_uri} .</code></li>
                    <li>在AWS Console的S3服务中搜索: <strong>{bucket}</strong></li>
                </ul>
            </div>
        </div>
        """
        
        return message, location_html, df
        
    except Exception as e:
        return f"❌ 获取结果失败: {str(e)}", "", None


def start_video_batch_job(
    use_jsonl: bool,
    input_bucket: str,
    input_prefix: str,
    jsonl_s3_uri: str,
    output_bucket: str,
    output_prefix: str,
    model_name: str,
    role_arn: str,
    system_prompt: str,
    user_prompt: str,
    aws_region: str = "us-west-2",
    progress=gr.Progress()
) -> tuple:
    """启动视频批处理任务（支持两种模式）"""
    # 初始化处理日志
    processing_log = []
    
    def log_callback(step: str, current: int, total: int, details: str):
        """进度回调函数"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        if step == 'scan':
            emoji = '🔍'
        elif step == 'process':
            emoji = '🎬'
            if total > 0:
                progress_pct = (current / total * 0.6) + 0.3
                progress(progress_pct, desc=f"处理视频 {current}/{total}")
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
        
        # 模式特定验证
        if use_jsonl:
            if not jsonl_s3_uri:
                return (
                    "❌ JSONL模式需要填写JSONL文件S3 URI",
                    None,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    ""
                )
        else:
            if not all([input_bucket, user_prompt]):
                return (
                    "❌ 原始视频模式需要填写输入Bucket和User Prompt",
                    None,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    ""
                )
        
        model_id = VIDEO_MODELS.get(model_name)
        if not model_id:
            return (
                "❌ 无效的模型选择",
                None,
                gr.update(visible=False),
                gr.update(visible=False),
                ""
            )
        
        progress(0, desc="正在初始化...")
        log_callback('init', 0, 0, '正在初始化视频批处理管理器...')
        
        # 创建管理器
        manager = create_batch_manager(bedrock_region=aws_region, s3_region=aws_region)
        
        # 根据模式选择不同的处理逻辑
        if use_jsonl:
            # JSONL文件模式：直接使用已有的JSONL文件
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
            
            log_callback('jsonl', 1, 1, '✅ 使用已有JSONL文件，跳过视频处理步骤')
        else:
            # 原始视频模式：读取视频并生成JSONL
            if not user_prompt:
                return (
                    "❌ 原始视频模式需要填写User Prompt",
                    None,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    ""
                )
            
            # 创建视频批处理任务（带进度回调）
            result = manager.create_video_batch_job(
                input_bucket=input_bucket,
                input_prefix=input_prefix,
                output_bucket=output_bucket,
                output_prefix=output_prefix,
                model_id=model_id,
                role_arn=role_arn,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
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
        current_job_info['job_type'] = 'video'  # 标记任务类型
        
        # 持久化保存任务状态到文件
        save_job_state(result['job_arn'], {
            'output_bucket': output_bucket,
            'output_prefix': output_prefix,
            'aws_region': aws_region,
            'input_bucket': input_bucket,
            'input_prefix': input_prefix,
            'job_type': 'video'
        })
        
        progress(1.0, desc="任务已提交...")
        log_callback('submit', 1, 1, f'✅ 视频批处理任务已成功提交到Bedrock')
        
        # 构建状态消息
        status_msg = f"""
### ✅ 视频批处理任务已提交

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
            f"❌ 启动视频批处理任务失败: {str(e)}",
            None,
            gr.update(visible=False),
            gr.update(visible=False),
            "\n".join(processing_log)
        )


def validate_text_single_inference(
    use_jsonl: bool,
    input_bucket: str,
    input_prefix: str,
    jsonl_s3_uri: str,
    prompt: str,
    model_name: str,
    aws_region: str
) -> str:
    """验证文本批处理的单次推理"""
    try:
        if not model_name:
            return "❌ 请选择模型"
        
        model_id = TEXT_MODELS.get(model_name)
        if not model_id:
            return "❌ 无效的模型选择"
        
        # 模式验证
        if use_jsonl:
            if not jsonl_s3_uri:
                return "❌ JSONL模式需要填写JSONL文件S3 URI"
        else:
            if not all([input_bucket, prompt]):
                return "❌ 原始文件模式需要填写输入Bucket和Prompt"
        
        manager = create_batch_manager(bedrock_region=aws_region, s3_region=aws_region)
        
        result = manager.validate_single_text_inference(
            use_jsonl=use_jsonl,
            input_bucket=input_bucket,
            input_prefix=input_prefix,
            jsonl_s3_uri=jsonl_s3_uri,
            prompt=prompt,
            model_id=model_id
        )
        
        if result['success']:
            return f"""
### ✅ 单次推理验证成功！

#### 📝 验证信息
- **验证文件**: {result['file_info']}
- **使用模型**: {model_name}
- **推理耗时**: {result['duration']:.2f}秒

#### 📊 Token统计
- **输入Tokens**: {result['input_tokens']}
- **输出Tokens**: {result['output_tokens']}
- **停止原因**: {result['stop_reason']}

#### 💬 模型输出
{result['output_text']}

---
💡 **提示**: 验证成功！Prompt组装和模型调用均正常，可以开始批处理任务。
"""
        else:
            return f"""
### ❌ 单次推理验证失败

**错误信息**: {result['error']}

---
💡 **提示**: 请检查配置参数和权限设置，修复问题后重新验证。
"""
    
    except Exception as e:
        return f"❌ 验证失败: {str(e)}"


def validate_image_single_inference(
    use_jsonl: bool,
    input_bucket: str,
    input_prefix: str,
    jsonl_s3_uri: str,
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    aws_region: str
) -> str:
    """验证图片批处理的单次推理"""
    try:
        if not model_name:
            return "❌ 请选择模型"
        
        model_id = IMAGE_MODELS.get(model_name)
        if not model_id:
            return "❌ 无效的模型选择"
        
        # 模式验证
        if use_jsonl:
            if not jsonl_s3_uri:
                return "❌ JSONL模式需要填写JSONL文件S3 URI"
        else:
            if not all([input_bucket, user_prompt]):
                return "❌ 原始图片模式需要填写输入Bucket和User Prompt"
        
        manager = create_batch_manager(bedrock_region=aws_region, s3_region=aws_region)
        
        result = manager.validate_single_image_inference(
            use_jsonl=use_jsonl,
            input_bucket=input_bucket,
            input_prefix=input_prefix,
            jsonl_s3_uri=jsonl_s3_uri,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_id=model_id
        )
        
        if result['success']:
            return f"""
### ✅ 单次推理验证成功！

#### 🖼️ 验证信息
- **验证文件**: {result['file_info']}
- **使用模型**: {model_name}
- **推理耗时**: {result['duration']:.2f}秒

#### 📊 Token统计
- **输入Tokens**: {result['input_tokens']}
- **输出Tokens**: {result['output_tokens']}
- **停止原因**: {result['stop_reason']}

#### 💬 模型输出
{result['output_text']}

---
💡 **提示**: 验证成功！图片处理和模型调用均正常，可以开始批处理任务。
"""
        else:
            return f"""
### ❌ 单次推理验证失败

**错误信息**: {result['error']}

---
💡 **提示**: 请检查配置参数、图片格式和权限设置，修复问题后重新验证。
"""
    
    except Exception as e:
        return f"❌ 验证失败: {str(e)}"


def validate_video_single_inference(
    use_jsonl: bool,
    input_bucket: str,
    input_prefix: str,
    jsonl_s3_uri: str,
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    aws_region: str
) -> str:
    """验证视频批处理的单次推理"""
    try:
        if not model_name:
            return "❌ 请选择模型"
        
        model_id = VIDEO_MODELS.get(model_name)
        if not model_id:
            return "❌ 无效的模型选择"
        
        # 模式验证
        if use_jsonl:
            if not jsonl_s3_uri:
                return "❌ JSONL模式需要填写JSONL文件S3 URI"
        else:
            if not all([input_bucket, user_prompt]):
                return "❌ 原始视频模式需要填写输入Bucket和User Prompt"
        
        manager = create_batch_manager(bedrock_region=aws_region, s3_region=aws_region)
        
        result = manager.validate_single_video_inference(
            use_jsonl=use_jsonl,
            input_bucket=input_bucket,
            input_prefix=input_prefix,
            jsonl_s3_uri=jsonl_s3_uri,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_id=model_id
        )
        
        if result['success']:
            return f"""
### ✅ 单次推理验证成功！

#### 🎬 验证信息
- **验证文件**: {result['file_info']}
- **使用模型**: {model_name}
- **推理耗时**: {result['duration']:.2f}秒

#### 📊 Token统计
- **输入Tokens**: {result['input_tokens']}
- **输出Tokens**: {result['output_tokens']}
- **停止原因**: {result['stop_reason']}

#### 💬 模型输出
{result['output_text']}

---
💡 **提示**: 验证成功！视频处理和模型调用均正常，可以开始批处理任务。
"""
        else:
            return f"""
### ❌ 单次推理验证失败

**错误信息**: {result['error']}

---
💡 **提示**: 请检查配置参数、视频格式和权限设置，修复问题后重新验证。
"""
    
    except Exception as e:
        return f"❌ 验证失败: {str(e)}"
