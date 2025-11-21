"""
任务管理模块
"""
import boto3
import json
import time
import logging
from datetime import datetime
from typing import Dict, List
from .s3_manager import S3Manager

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - [JobManager] - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class JobManager:
    """处理Bedrock批处理任务的状态管理和结果获取"""
    
    def __init__(self, bedrock_region: str, s3_manager: S3Manager):
        """
        初始化任务管理器
        
        Args:
            bedrock_region: Bedrock服务所在区域
            s3_manager: S3管理器实例
        """
        self.bedrock = boto3.client('bedrock', region_name=bedrock_region)
        self.s3_manager = s3_manager
        self.current_jobs = {}
    
    def create_job(
        self,
        jsonl_s3_uri: str,
        output_bucket: str,
        output_prefix: str,
        model_id: str,
        role_arn: str,
        job_name: str = None
    ) -> Dict:
        """
        创建批量推理任务
        
        Args:
            jsonl_s3_uri: JSONL文件的S3 URI
            output_bucket: 输出bucket名称
            output_prefix: 输出路径前缀
            model_id: 模型ID
            role_arn: IAM角色ARN
            job_name: 任务名称（可选）
            
        Returns:
            任务信息字典
        """
        logger.info(f"🚀 开始创建批量推理任务")
        logger.debug(f"参数 - JSONL URI: {jsonl_s3_uri}")
        logger.debug(f"参数 - Output Bucket: {output_bucket}, Output Prefix: {output_prefix}")
        logger.debug(f"参数 - Model ID: {model_id}")
        try:
            # 配置输入输出
            input_data_config = {
                "s3InputDataConfig": {
                    "s3Uri": jsonl_s3_uri
                }
            }
            
            # 构建输出URI
            if output_prefix:
                output_s3_uri = f"s3://{output_bucket}/{output_prefix}"
            else:
                output_s3_uri = f"s3://{output_bucket}/"
            
            output_data_config = {
                "s3OutputDataConfig": {
                    "s3Uri": output_s3_uri
                }
            }
            
            # 生成任务名称
            if not job_name:
                job_name = f"batch-job-{int(datetime.now().timestamp())}"
            
            logger.debug(f"任务名称: {job_name}")
            logger.debug(f"输出S3 URI: {output_s3_uri}")
            
            # 提交批量推理任务
            logger.info(f"📤 向Bedrock提交创建模型调用任务请求...")
            response = self.bedrock.create_model_invocation_job(
                roleArn=role_arn,
                modelId=model_id,
                jobName=job_name,
                inputDataConfig=input_data_config,
                outputDataConfig=output_data_config
            )
            
            job_arn = response.get('jobArn')
            logger.info(f"✅ 批量推理任务创建成功! Job ARN: {job_arn}")
            logger.debug(f"完整响应: {response}")
            
            # 保存任务信息
            self.current_jobs[job_arn] = {
                'job_arn': job_arn,
                'job_name': job_name,
                'model_id': model_id,
                'status': 'Submitted',
                'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'output_bucket': output_bucket,
                'output_prefix': output_prefix,
                'input_jsonl_uri': jsonl_s3_uri
            }
            logger.debug(f"任务信息已保存到内存")
            
            return {
                'success': True,
                'job_arn': job_arn,
                'job_name': job_name,
                'message': f"成功提交批量推理任务"
            }
            
        except Exception as e:
            logger.error(f"❌ 创建批量任务失败: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': f"创建批量任务失败: {str(e)}"
            }
    
    def get_job_status(self, job_arn: str) -> Dict:
        """
        获取任务状态
        
        Args:
            job_arn: 任务ARN
            
        Returns:
            任务状态信息
        """
        try:
            logger.debug(f"🔍 查询任务状态: {job_arn}")
            response = self.bedrock.get_model_invocation_job(jobIdentifier=job_arn)
            
            status = response.get('status')
            logger.info(f"📊 任务状态: {status}")
            logger.debug(f"Submit Time: {response.get('submitTime', 'N/A')}, Last Modified: {response.get('lastModifiedTime', 'N/A')}")
            
            job_info = {
                'job_arn': job_arn,
                'status': status,
                'submit_time': response.get('submitTime', ''),
                'last_modified': response.get('lastModifiedTime', ''),
                'message': response.get('message', ''),
            }
            
            # 如果任务完成，获取统计信息
            if status == 'Completed':
                if 'outputDataConfig' in response:
                    output_uri = response['outputDataConfig']['s3OutputDataConfig']['s3Uri']
                    job_info['output_s3_uri'] = output_uri
                    logger.info(f"✅ 任务已完成! 输出位置: {output_uri}")
            
            return job_info
            
        except Exception as e:
            logger.error(f"❌ 获取任务状态失败: {str(e)}", exc_info=True)
            return {
                'job_arn': job_arn,
                'status': 'Error',
                'error': str(e)
            }
    
    def monitor_job(self, job_arn: str, check_interval: int = 30) -> Dict:
        """
        监控任务直到完成或失败
        
        Args:
            job_arn: 任务ARN
            check_interval: 检查间隔（秒）
            
        Returns:
            最终任务状态
        """
        while True:
            status_info = self.get_job_status(job_arn)
            status = status_info.get('status')
            
            if status in ['Completed', 'Failed', 'Stopped']:
                return status_info
            
            time.sleep(check_interval)
    
    def get_results_preview(self, job_arn: str, output_bucket: str, output_prefix: str, max_preview_lines: int = 3) -> Dict:
        """
        获取任务结果预览和文件位置
        
        Args:
            job_arn: 任务ARN
            output_bucket: 输出bucket名称（仅用于兼容，实际从API获取）
            output_prefix: 输出路径前缀（仅用于兼容，实际从API获取）
            max_preview_lines: 最大预览行数，默认3行（文本/图片），视频建议1行
            
        Returns:
            包含预览数据和文件位置的字典
        """
        logger.info(f"📥 开始获取任务结果: {job_arn}")
        try:
            # 首先获取任务状态，从中获取实际的输出S3 URI
            logger.debug(f"步骤1: 获取任务状态...")
            job_status = self.get_job_status(job_arn)
            
            if job_status.get('status') != 'Completed':
                raise Exception(f"任务状态为 {job_status.get('status')}，请等待任务完成")
            
            # 从任务信息中获取实际的输出S3 URI
            output_s3_uri = job_status.get('output_s3_uri')
            logger.debug(f"步骤2: 解析输出S3 URI: {output_s3_uri}")
            if not output_s3_uri:
                raise Exception("无法从任务信息中获取输出S3 URI")
            
            # 解析S3 URI: s3://bucket/prefix/job_id/
            # 移除 s3:// 前缀
            s3_path = output_s3_uri.replace('s3://', '')
            
            # 分离bucket和prefix
            parts = s3_path.split('/', 1)
            actual_bucket = parts[0]
            actual_prefix = parts[1] if len(parts) > 1 else ''
            
            # 确保prefix以/结尾（如果不为空）
            if actual_prefix and not actual_prefix.endswith('/'):
                actual_prefix += '/'
            
            # 获取job_id
            job_id = job_arn.split('/')[-1]
            
            logger.debug(f"步骤3: 解析S3位置 - Bucket: {actual_bucket}, Prefix: {actual_prefix}, Job ID: {job_id}")
            
            # Bedrock会在输出路径下创建job_id子目录
            # 实际结果文件路径：actual_prefix + job_id + /
            result_prefix = f"{actual_prefix}{job_id}/"
            logger.debug(f"完整结果路径: s3://{actual_bucket}/{result_prefix}")
            
            results = []
            result_file_key = None
            
            # 查找结果文件 - 列出所有文件以便调试
            logger.debug(f"步骤4: 列举S3结果目录中的文件...")
            response = self.s3_manager.s3.list_objects_v2(
                Bucket=actual_bucket,
                Prefix=result_prefix
            )
            
            # 记录所有找到的文件用于调试
            all_files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    all_files.append(obj['Key'])
            
            logger.debug(f"找到 {len(all_files)} 个文件: {all_files}")
            
            # 查找结果文件和manifest文件
            manifest_file_key = None
            manifest_data = None
            
            if 'Contents' in response:
                # 查找.out文件（包括manifest和结果文件）
                logger.debug(f"步骤5: 搜索结果文件和manifest文件...")
                candidate_files = []
                
                for obj in response['Contents']:
                    key = obj['Key']
                    
                    # 跳过目录本身
                    if key.endswith('/'):
                        logger.debug(f"跳过目录: {key}")
                        continue
                    
                    # 查找manifest文件
                    if 'manifest.json.out' in key.lower():
                        manifest_file_key = key
                        logger.debug(f"找到manifest文件: {key}")
                        continue
                    
                    # 收集所有.jsonl.out文件作为候选
                    if key.endswith('.jsonl.out'):
                        candidate_files.append(key)
                        logger.debug(f"候选结果文件: {key}")
                
                # .jsonl.out文件就是输出文件，直接使用第一个找到的
                if candidate_files:
                    result_file_key = candidate_files[0]
                    logger.info(f"✅ 找到输出文件: {result_file_key}")
                
                # 读取manifest文件
                if manifest_file_key:
                    try:
                        logger.debug(f"读取manifest文件: {manifest_file_key}")
                        manifest_response = self.s3_manager.s3.get_object(
                            Bucket=actual_bucket,
                            Key=manifest_file_key
                        )
                        manifest_content = manifest_response['Body'].read().decode('utf-8')
                        manifest_data = json.loads(manifest_content)
                        logger.info(f"✅ 成功读取manifest文件")
                        logger.debug(f"Manifest内容: {json.dumps(manifest_data, indent=2)}")
                    except Exception as e:
                        logger.warning(f"⚠️ 读取manifest文件失败: {str(e)}")
                        manifest_data = None
                
                if result_file_key:
                    logger.info(f"✅ 最终选择结果文件: {result_file_key}")
                    
                    # 使用流式读取，逐行解析，避免JSON截断
                    try:
                        logger.debug(f"开始流式读取结果文件...")
                        file_response = self.s3_manager.s3.get_object(
                            Bucket=actual_bucket,
                            Key=result_file_key
                        )
                        
                        # 使用readline()逐行读取
                        body_stream = file_response['Body']
                        lines_processed = 0
                        max_lines = max_preview_lines  # 使用参数指定的预览行数
                        
                        # 逐行读取文件
                        while lines_processed < max_lines:
                            line_bytes = body_stream.readline()
                            if not line_bytes:  # 到达文件末尾
                                logger.debug("已到达文件末尾")
                                break
                            
                            try:
                                line = line_bytes.decode('utf-8').strip()
                                if not line:  # 跳过空行
                                    continue
                                
                                lines_processed += 1
                                logger.debug(f"读取第 {lines_processed} 行，长度: {len(line)} 字符")
                                
                                # 解析JSON
                                result = json.loads(line)
                                
                                # 检查是成功输出还是错误
                                if 'modelOutput' in result:
                                    # 判断是Claude格式还是Nova格式
                                    model_output = result['modelOutput']
                                    
                                    if 'content' in model_output:
                                        # Claude格式：直接有content
                                        output_text = model_output['content'][0]['text']
                                        stop_reason = model_output.get('stop_reason', 'unknown')
                                    elif 'output' in model_output and 'message' in model_output['output']:
                                        # Nova格式：output.message.content
                                        output_text = model_output['output']['message']['content'][0]['text']
                                        stop_reason = model_output.get('stopReason', 'unknown')
                                    else:
                                        logger.warning(f"第 {lines_processed} 行modelOutput格式无法识别")
                                        continue
                                    
                                    # 成功的输出
                                    parsed_result = {
                                        'record_id': result.get('recordId'),
                                        'output_text': output_text,
                                        'stop_reason': stop_reason,
                                        'has_error': False
                                    }
                                    results.append(parsed_result)
                                    logger.debug(f"✓ 成功解析第 {lines_processed} 行")
                                elif 'error' in result:
                                    # 包含错误信息
                                    error_info = result['error']
                                    error_msg = f"错误码{error_info.get('errorCode', 'N/A')}: {error_info.get('errorMessage', '未知错误')}"
                                    parsed_result = {
                                        'record_id': result.get('recordId'),
                                        'output_text': f"[处理失败] {error_msg}",
                                        'stop_reason': 'error',
                                        'has_error': True,
                                        'error_code': error_info.get('errorCode'),
                                        'error_message': error_info.get('errorMessage'),
                                        'retryable': error_info.get('retryable', False)
                                    }
                                    results.append(parsed_result)
                                    logger.warning(f"⚠️ 第 {lines_processed} 行包含错误: {error_msg}")
                                else:
                                    logger.warning(f"第 {lines_processed} 行格式不正确，既无modelOutput也无error")
                            
                            except json.JSONDecodeError as e:
                                logger.warning(f"第 {lines_processed} 行JSON解析失败: {str(e)}")
                                continue
                            except Exception as e:
                                logger.warning(f"第 {lines_processed} 行处理失败: {str(e)}")
                                continue
                        
                        logger.info(f"流式读取完成，共处理 {lines_processed} 行，成功解析 {len(results)} 条结果")
                        
                    except Exception as e:
                        logger.error(f"流式读取文件失败: {str(e)}")
            
            # 如果没有找到.jsonl.out文件，尝试其他可能的文件名格式
            if not results and all_files:
                for file_key in all_files:
                    if file_key.endswith('/') or 'manifest' in file_key.lower():
                        continue
                    
                    # 尝试任何非目录文件
                    try:
                        file_response = self.s3_manager.s3.get_object(
                            Bucket=actual_bucket,
                            Key=file_key
                        )
                        content = file_response['Body'].read(51200).decode('utf-8')
                        
                        # 解析前5行
                        lines = content.strip().split('\n')
                        
                        for line in lines[:5]:
                            if line.strip():
                                try:
                                    result = json.loads(line)
                                    if 'modelOutput' in result:
                                        model_output = result['modelOutput']
                                        # 支持Claude和Nova两种格式
                                        if 'content' in model_output:
                                            output_text = model_output['content'][0]['text']
                                            stop_reason = model_output.get('stop_reason', 'unknown')
                                        elif 'output' in model_output:
                                            output_text = model_output['output']['message']['content'][0]['text']
                                            stop_reason = model_output.get('stopReason', 'unknown')
                                        else:
                                            continue
                                        
                                        parsed_result = {
                                            'record_id': result.get('recordId'),
                                            'output_text': output_text,
                                            'stop_reason': stop_reason
                                        }
                                        results.append(parsed_result)
                                except Exception:
                                    continue
                        
                        if results:
                            result_file_key = file_key
                            break
                    except Exception:
                        continue
            
            # 检查是否找到并成功解析结果
            if not result_file_key:
                # 情况1: 没有找到结果文件
                files_info = f"找到的文件: {', '.join(all_files)}" if all_files else "目录下没有文件"
                error_msg = (
                    f"未找到结果文件\n"
                    f"- 查找路径: s3://{actual_bucket}/{result_prefix}\n"
                    f"- 原始输出URI: {output_s3_uri}\n"
                    f"- Job ID: {job_id}\n"
                    f"- {files_info}"
                )
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            if not results:
                # 情况2: 找到了文件但解析失败
                logger.warning(f"⚠️ 找到结果文件但解析失败，尝试返回文件位置")
                # 即使解析失败，也返回文件位置信息
                s3_uri = f"s3://{actual_bucket}/{result_file_key}"
                logger.info(f"返回文件位置（无预览数据）: {s3_uri}")
                return {
                    'preview': [],
                    's3_uri': s3_uri,
                    'file_name': result_file_key.split('/')[-1],
                    'bucket': actual_bucket,
                    'key': result_file_key,
                    'parse_warning': '结果文件已找到，但预览数据解析失败。请直接访问S3文件获取完整结果。'
                }
            
            # 构建S3 URI
            s3_uri = f"s3://{actual_bucket}/{result_file_key}"
            manifest_s3_uri = f"s3://{actual_bucket}/{manifest_file_key}" if manifest_file_key else None
            logger.info(f"✅ 结果获取完成! 共{len(results)}条预览记录, S3 URI: {s3_uri}")
            
            result_dict = {
                'preview': results,
                's3_uri': s3_uri,
                'file_name': result_file_key.split('/')[-1],
                'bucket': actual_bucket,
                'key': result_file_key
            }
            
            # 添加manifest信息
            if manifest_data:
                result_dict['manifest'] = manifest_data
                result_dict['manifest_s3_uri'] = manifest_s3_uri
                logger.info(f"✅ 包含manifest信息")
            
            return result_dict
            
        except Exception as e:
            logger.error(f"❌ 获取任务结果失败: {str(e)}", exc_info=True)
            raise Exception(f"获取任务结果失败: {str(e)}")
