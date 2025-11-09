"""
AWS Bedrock Batch Inference Manager
处理批量推理任务的创建、监控和结果获取
"""
import boto3
import json
import os
from datetime import datetime
import time
from typing import Dict, List, Tuple, Optional, Callable


class BatchInferenceManager:
    """管理AWS Bedrock批量推理任务"""
    
    def __init__(self, bedrock_region: str = 'us-east-1', s3_region: str = 'us-east-1'):
        """
        初始化批量推理管理器
        
        Args:
            bedrock_region: Bedrock服务所在区域
            s3_region: S3 bucket所在区域
        """
        self.bedrock_region = bedrock_region
        self.s3_region = s3_region
        self.bedrock = boto3.client('bedrock', region_name=bedrock_region)
        self.s3 = boto3.client('s3', region_name=s3_region)
        # STS客户端使用s3_region，因为主要用于验证S3权限
        self.sts = boto3.client('sts', region_name=s3_region)
        self.current_jobs = {}
        
    def list_input_files(self, bucket_name: str, prefix: str) -> List[Dict]:
        """
        列出输入bucket中的文件
        
        Args:
            bucket_name: S3 bucket名称
            prefix: 文件路径前缀
            
        Returns:
            文件列表，包含文件路径、大小等信息
        """
        try:
            files = []
            response = self.s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            
            if 'Contents' not in response:
                return files
                
            for obj in response['Contents']:
                # 跳过目录本身
                if obj['Key'] == prefix or obj['Key'].endswith('/'):
                    continue
                    
                files.append({
                    'file_path': obj['Key'],
                    'file_name': os.path.basename(obj['Key']),
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S')
                })
            
            return files
            
        except Exception as e:
            raise Exception(f"列出文件失败: {str(e)}")
    
    def read_file_content(self, bucket_name: str, file_path: str) -> str:
        """
        读取S3文件内容
        
        Args:
            bucket_name: S3 bucket名称
            file_path: 文件路径
            
        Returns:
            文件内容字符串
        """
        try:
            response = self.s3.get_object(Bucket=bucket_name, Key=file_path)
            content = response['Body'].read().decode('utf-8')
            return content
        except Exception as e:
            raise Exception(f"读取文件失败 {file_path}: {str(e)}")
    
    def prepare_batch_data(
        self, 
        bucket_name: str, 
        prefix: str, 
        prompt: str,
        model_id: str,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        progress_callback: Optional[Callable] = None
    ) -> Tuple[List[Dict], str]:
        """
        准备批量推理的数据
        
        Args:
            bucket_name: 输入bucket名称
            prefix: 文件路径前缀
            prompt: 用户提供的prompt提示词
            model_id: 模型ID
            max_tokens: 最大token数
            temperature: 温度参数
            progress_callback: 进度回调函数，接收(step, current, total, details)参数
            
        Returns:
            (model_inputs列表, 临时JSONL文件名)
        """
        try:
            # 步骤1: 扫描文件
            if progress_callback:
                progress_callback('scan', 0, 0, '正在扫描输入文件...')
            
            # 获取所有文件
            files = self.list_input_files(bucket_name, prefix)
            
            if not files:
                raise Exception(f"在 {bucket_name}/{prefix} 中未找到任何文件")
            
            total_files = len(files)
            if progress_callback:
                progress_callback('scan', total_files, total_files, f'发现 {total_files} 个文件待处理')
            
            model_inputs = []
            
            # 步骤2: 处理每个文件
            for idx, file_info in enumerate(files, 1):
                file_path = file_info['file_path']
                file_name = file_info['file_name']
                file_size = file_info['size']
                
                # 格式化文件大小
                if file_size < 1024:
                    size_str = f"{file_size}B"
                elif file_size < 1024 * 1024:
                    size_str = f"{file_size / 1024:.1f}KB"
                else:
                    size_str = f"{file_size / (1024 * 1024):.1f}MB"
                
                if progress_callback:
                    progress_callback('process', idx, total_files, 
                                    f'正在处理: {file_name} ({size_str})')
                
                # 读取文件内容
                file_content = self.read_file_content(bucket_name, file_path)
                
                # 生成唯一的记录ID
                record_id = f"{int(datetime.now().timestamp())}_{len(model_inputs)}"
                
                # 组合prompt和文件内容
                input_text = f"{prompt}\n\n原始文本:\n{file_content}"
                
                # 准备模型输入（使用Anthropic Claude格式）
                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": input_text
                                }
                            ]
                        }
                    ]
                }
                
                model_input = {
                    "recordId": record_id,
                    "modelInput": body
                }
                
                model_inputs.append(model_input)
                
                if progress_callback:
                    progress_callback('process', idx, total_files, 
                                    f'已完成: {file_name} ({size_str})')
            
            # 步骤3: 生成JSONL文件
            if progress_callback:
                progress_callback('generate', 0, 1, '正在生成批处理JSONL文件...')
            
            # 生成临时文件名
            timestamp = int(datetime.now().timestamp())
            filename = f'batch-{timestamp}.jsonl'
            
            # 写入本地临时文件
            with open(filename, 'w', encoding='utf-8') as f:
                for item in model_inputs:
                    json_str = json.dumps(item, ensure_ascii=False)
                    f.write(json_str + '\n')
            
            if progress_callback:
                progress_callback('generate', 1, 1, f'JSONL文件生成完成: {filename}')
            
            return model_inputs, filename
            
        except Exception as e:
            if progress_callback:
                progress_callback('error', 0, 0, f'处理失败: {str(e)}')
            raise Exception(f"准备批量数据失败: {str(e)}")
    
    def normalize_prefix(self, prefix: str) -> str:
        """
        规范化S3前缀，确保格式正确
        
        Args:
            prefix: 原始前缀
            
        Returns:
            规范化后的前缀
        """
        if not prefix:
            return ""
        
        # 移除开头的'/'
        prefix = prefix.lstrip('/')
        
        # 确保结尾有'/'（如果前缀不为空）
        if prefix and not prefix.endswith('/'):
            prefix += '/'
            
        return prefix
    
    def upload_local_files(
        self, 
        local_files: List[str], 
        bucket_name: str, 
        prefix: str = "raw_data"
    ) -> List[str]:
        """
        上传本地文件到S3的raw_data目录
        
        Args:
            local_files: 本地文件路径列表
            bucket_name: S3 bucket名称
            prefix: S3路径前缀（默认为raw_data）
            
        Returns:
            上传后的S3文件路径列表
        """
        try:
            prefix = self.normalize_prefix(prefix)
            uploaded_files = []
            
            for local_file in local_files:
                if not os.path.exists(local_file):
                    raise Exception(f"本地文件不存在: {local_file}")
                
                # 获取文件名
                filename = os.path.basename(local_file)
                
                # 生成S3 key
                s3_key = f"{prefix}{filename}"
                
                # 上传文件
                self.s3.upload_file(local_file, bucket_name, s3_key)
                uploaded_files.append(s3_key)
            
            return uploaded_files
            
        except Exception as e:
            raise Exception(f"上传本地文件失败: {str(e)}")
    
    def upload_to_s3(self, local_file: str, bucket_name: str, s3_key: str) -> str:
        """
        上传文件到S3
        
        Args:
            local_file: 本地文件路径
            bucket_name: S3 bucket名称
            s3_key: S3对象键
            
        Returns:
            S3 URI
        """
        try:
            self.s3.upload_file(local_file, bucket_name, s3_key)
            s3_uri = f"s3://{bucket_name}/{s3_key}"
            return s3_uri
        except Exception as e:
            raise Exception(f"上传文件到S3失败: {str(e)}")
    
    def create_batch_job_from_jsonl(
        self,
        jsonl_s3_uri: str,
        output_bucket: str,
        output_prefix: str,
        model_id: str,
        role_arn: str,
        job_name: Optional[str] = None
    ) -> Dict:
        """
        使用已有的JSONL文件创建批量推理任务
        
        Args:
            jsonl_s3_uri: JSONL文件的S3 URI (例如: s3://bucket/path/file.jsonl)
            output_bucket: 输出bucket名称
            output_prefix: 输出路径前缀
            model_id: 模型ID
            role_arn: IAM角色ARN
            job_name: 任务名称（可选）
            
        Returns:
            任务信息字典
        """
        try:
            # 规范化输出前缀
            output_prefix = self.normalize_prefix(output_prefix)
            
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
            
            # 提交批量推理任务
            response = self.bedrock.create_model_invocation_job(
                roleArn=role_arn,
                modelId=model_id,
                jobName=job_name,
                inputDataConfig=input_data_config,
                outputDataConfig=output_data_config
            )
            
            job_arn = response.get('jobArn')
            
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
            
            return {
                'success': True,
                'job_arn': job_arn,
                'job_name': job_name,
                'message': f"成功提交批量推理任务（使用已有JSONL文件）"
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f"创建批量任务失败: {str(e)}"
            }
    
    def create_batch_job(
        self,
        input_bucket: str,
        input_prefix: str,
        output_bucket: str,
        output_prefix: str,
        model_id: str,
        role_arn: str,
        prompt: str,
        job_name: Optional[str] = None,
        local_files: Optional[List[str]] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """
        创建批量推理任务
        
        Args:
            input_bucket: 输入bucket名称
            input_prefix: 输入路径前缀
            output_bucket: 输出bucket名称
            output_prefix: 输出路径前缀
            model_id: 模型ID
            role_arn: IAM角色ARN
            prompt: 处理提示词
            job_name: 任务名称（可选）
            local_files: 本地文件列表（可选，如果提供则先上传到S3）
            progress_callback: 进度回调函数（可选）
            
        Returns:
            任务信息字典
        """
        try:
            # 如果提供了本地文件，先上传到raw_data目录
            if local_files:
                if progress_callback:
                    progress_callback('upload', 0, len(local_files), '正在上传本地文件到S3...')
                    
                raw_data_prefix = self.normalize_prefix(input_prefix) + "raw_data"
                uploaded_files = self.upload_local_files(
                    local_files, 
                    input_bucket, 
                    raw_data_prefix
                )
                # 使用raw_data目录作为输入前缀
                input_prefix = raw_data_prefix
                
                if progress_callback:
                    progress_callback('upload', len(local_files), len(local_files), 
                                    f'已上传 {len(local_files)} 个本地文件')
            
            # 规范化前缀
            input_prefix = self.normalize_prefix(input_prefix)
            output_prefix = self.normalize_prefix(output_prefix)
            
            # 准备批量数据（带进度回调）
            model_inputs, filename = self.prepare_batch_data(
                input_bucket, 
                input_prefix, 
                prompt,
                model_id,
                progress_callback=progress_callback
            )
            
            # 上传JSONL文件到S3
            # 避免双斜杠：input_prefix已经有尾部斜杠或为空
            if input_prefix:
                s3_key = f"{input_prefix}{filename}"
            else:
                s3_key = filename
            input_s3_uri = self.upload_to_s3(filename, input_bucket, s3_key)
            
            # 记录JSONL文件位置
            if progress_callback:
                progress_callback('upload', 1, 1, f'✅ JSONL文件已上传到: {input_s3_uri}')
            
            # 清理本地临时文件
            if os.path.exists(filename):
                os.remove(filename)
            
            # 配置输入输出
            input_data_config = {
                "s3InputDataConfig": {
                    "s3Uri": input_s3_uri
                }
            }
            
            # 构建输出URI，避免双斜杠
            if output_prefix:
                # output_prefix已经有尾部斜杠
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
            
            # 提交批量推理任务
            response = self.bedrock.create_model_invocation_job(
                roleArn=role_arn,
                modelId=model_id,
                jobName=job_name,
                inputDataConfig=input_data_config,
                outputDataConfig=output_data_config
            )
            
            job_arn = response.get('jobArn')
            
            # 保存任务信息
            self.current_jobs[job_arn] = {
                'job_arn': job_arn,
                'job_name': job_name,
                'model_id': model_id,
                'status': 'Submitted',
                'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'input_files_count': len(model_inputs),
                'output_bucket': output_bucket,
                'output_prefix': output_prefix,
                'input_file': filename
            }
            
            return {
                'success': True,
                'job_arn': job_arn,
                'job_name': job_name,
                'message': f"成功提交批量推理任务，共{len(model_inputs)}个文件"
            }
            
        except Exception as e:
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
            response = self.bedrock.get_model_invocation_job(jobIdentifier=job_arn)
            
            status = response.get('status')
            
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
                    job_info['output_s3_uri'] = response['outputDataConfig']['s3OutputDataConfig']['s3Uri']
            
            return job_info
            
        except Exception as e:
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
    
    def get_job_results(self, job_arn: str, output_bucket: str, output_prefix: str) -> List[Dict]:
        """
        获取任务结果
        
        Args:
            job_arn: 任务ARN
            output_bucket: 输出bucket名称
            output_prefix: 输出路径前缀
            
        Returns:
            结果列表
        """
        try:
            # 获取job_id
            job_id = job_arn.split('/')[-1]
            
            # 构建输出文件路径
            # Bedrock会在output_prefix下创建以job_id命名的文件夹
            # 避免双斜杠：output_prefix已经规范化（有尾部斜杠或为空）
            if output_prefix:
                output_file_prefix = f"{output_prefix}{job_id}/"
            else:
                output_file_prefix = f"{job_id}/"
            
            # 列出输出文件
            response = self.s3.list_objects_v2(
                Bucket=output_bucket, 
                Prefix=output_file_prefix
            )
            
            results = []
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    # 查找.out文件
                    if obj['Key'].endswith('.out'):
                        # 读取结果文件
                        file_response = self.s3.get_object(
                            Bucket=output_bucket, 
                            Key=obj['Key']
                        )
                        content = file_response['Body'].read().decode('utf-8')
                        
                        # 解析JSONL格式
                        for line in content.strip().split('\n'):
                            if line:
                                result = json.loads(line)
                                results.append({
                                    'record_id': result.get('recordId'),
                                    'output_text': result['modelOutput']['content'][0]['text'],
                                    'input_tokens': result['modelOutput']['usage']['input_tokens'],
                                    'output_tokens': result['modelOutput']['usage']['output_tokens'],
                                    'stop_reason': result['modelOutput']['stop_reason']
                                })
            
            return results
            
        except Exception as e:
            raise Exception(f"获取任务结果失败: {str(e)}")
    
    def get_results_preview_and_download(self, job_arn: str, output_bucket: str, output_prefix: str) -> Dict:
        """
        获取任务结果预览和下载链接
        
        Args:
            job_arn: 任务ARN
            output_bucket: 输出bucket名称
            output_prefix: 输出路径前缀
            
        Returns:
            包含统计信息、预览数据和下载链接的字典
        """
        try:
            # 获取job_id
            job_id = job_arn.split('/')[-1]
            
            # 尝试多种可能的路径组合查找结果文件
            possible_prefixes = []
            
            # 规范化 output_prefix
            normalized_prefix = self.normalize_prefix(output_prefix) if output_prefix else ""
            
            # 构建可能的路径列表
            if normalized_prefix:
                # 路径1: output_prefix + job_id/
                possible_prefixes.append(f"{normalized_prefix}{job_id}/")
                # 路径2: output_prefix (直接在prefix下)
                possible_prefixes.append(normalized_prefix)
                # 路径3: output_prefix + job_id (没有尾部斜杠)
                possible_prefixes.append(f"{normalized_prefix}{job_id}")
            else:
                # 路径4: 只有job_id/
                possible_prefixes.append(f"{job_id}/")
                # 路径5: 只有job_id
                possible_prefixes.append(job_id)
            
            # 调试信息：记录尝试的路径
            print(f"[DEBUG] 正在查找结果文件，Job ID: {job_id}")
            print(f"[DEBUG] 将尝试以下路径: {possible_prefixes}")
            
            results = []
            result_file_key = None
            found_prefix = None
            
            # 依次尝试每个可能的路径
            for prefix in possible_prefixes:
                print(f"[DEBUG] 尝试路径: s3://{output_bucket}/{prefix}")
                
                try:
                    response = self.s3.list_objects_v2(
                        Bucket=output_bucket, 
                        Prefix=prefix
                    )
                    
                    if 'Contents' in response:
                        print(f"[DEBUG] 在路径 {prefix} 下找到 {len(response['Contents'])} 个文件")
                        
                        # 列出找到的文件（用于调试）
                        for obj in response['Contents']:
                            print(f"[DEBUG]   - {obj['Key']}")
                            
                            # 查找.out文件
                            if obj['Key'].endswith('.out') or obj['Key'].endswith('.jsonl.out'):
                                result_file_key = obj['Key']
                                found_prefix = prefix
                                print(f"[DEBUG] ✓ 找到结果文件: {result_file_key}")
                                
                                # 读取结果文件
                                file_response = self.s3.get_object(
                                    Bucket=output_bucket, 
                                    Key=obj['Key']
                                )
                                content = file_response['Body'].read().decode('utf-8')
                                
                                # 解析JSONL格式
                                for line in content.strip().split('\n'):
                                    if line:
                                        result = json.loads(line)
                                        results.append({
                                            'record_id': result.get('recordId'),
                                            'output_text': result['modelOutput']['content'][0]['text'],
                                            'input_tokens': result['modelOutput']['usage']['input_tokens'],
                                            'output_tokens': result['modelOutput']['usage']['output_tokens'],
                                            'stop_reason': result['modelOutput']['stop_reason']
                                        })
                                
                                # 找到结果后立即退出循环
                                break
                        
                        # 如果已经找到结果，退出外层循环
                        if results:
                            break
                    else:
                        print(f"[DEBUG] 路径 {prefix} 下没有文件")
                        
                except Exception as e:
                    print(f"[DEBUG] 检查路径 {prefix} 时出错: {str(e)}")
                    continue
            
            # 如果没有找到结果，提供详细的调试信息
            if not results:
                # 列出整个输出bucket的结构以帮助调试
                debug_info = self._debug_s3_structure(output_bucket, normalized_prefix, job_id)
                error_msg = f"未找到结果文件\n\n调试信息:\n"
                error_msg += f"- Job ID: {job_id}\n"
                error_msg += f"- 输出Bucket: {output_bucket}\n"
                error_msg += f"- 输出前缀: {normalized_prefix or '(根目录)'}\n"
                error_msg += f"- 尝试的路径: {', '.join(possible_prefixes)}\n\n"
                error_msg += f"S3目录结构:\n{debug_info}"
                raise Exception(error_msg)
            
            print(f"[DEBUG] ✓ 成功解析 {len(results)} 条结果记录")
            
            # 计算统计信息
            total_records = len(results)
            total_input_tokens = sum(r['input_tokens'] for r in results)
            total_output_tokens = sum(r['output_tokens'] for r in results)
            
            # 生成预签名下载URL（有效期1小时）
            download_url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': output_bucket, 'Key': result_file_key},
                ExpiresIn=3600
            )
            
            return {
                'stats': {
                    'total_records': total_records,
                    'total_input_tokens': total_input_tokens,
                    'total_output_tokens': total_output_tokens,
                    'total_tokens': total_input_tokens + total_output_tokens
                },
                'preview': results[:5],  # 前5行预览
                'download_url': download_url,
                'file_name': result_file_key.split('/')[-1]
            }
            
        except Exception as e:
            raise Exception(f"获取任务结果失败: {str(e)}")
    
    def _debug_s3_structure(self, bucket: str, prefix: str, job_id: str) -> str:
        """
        调试S3文件结构，帮助定位结果文件
        
        Args:
            bucket: S3 bucket名称
            prefix: 路径前缀
            job_id: 任务ID
            
        Returns:
            格式化的S3目录结构字符串
        """
        try:
            debug_lines = []
            
            # 尝试列出与job_id相关的所有文件
            # 1. 尝试列出prefix下的所有文件
            if prefix:
                debug_lines.append(f"\n1. 检查前缀路径: s3://{bucket}/{prefix}")
                try:
                    response = self.s3.list_objects_v2(
                        Bucket=bucket,
                        Prefix=prefix,
                        MaxKeys=100
                    )
                    if 'Contents' in response:
                        debug_lines.append(f"   找到 {len(response['Contents'])} 个文件:")
                        for obj in response['Contents'][:20]:  # 只显示前20个
                            debug_lines.append(f"   - {obj['Key']}")
                        if len(response['Contents']) > 20:
                            debug_lines.append(f"   ... 还有 {len(response['Contents']) - 20} 个文件")
                    else:
                        debug_lines.append("   (空目录)")
                except Exception as e:
                    debug_lines.append(f"   错误: {str(e)}")
            
            # 2. 搜索包含job_id的文件
            debug_lines.append(f"\n2. 搜索包含Job ID的文件: {job_id}")
            try:
                # 列出整个bucket（限制结果数量）
                response = self.s3.list_objects_v2(
                    Bucket=bucket,
                    MaxKeys=1000
                )
                if 'Contents' in response:
                    matching_files = [obj for obj in response['Contents'] if job_id in obj['Key']]
                    if matching_files:
                        debug_lines.append(f"   找到 {len(matching_files)} 个包含Job ID的文件:")
                        for obj in matching_files[:10]:  # 只显示前10个
                            debug_lines.append(f"   - {obj['Key']}")
                        if len(matching_files) > 10:
                            debug_lines.append(f"   ... 还有 {len(matching_files) - 10} 个文件")
                    else:
                        debug_lines.append(f"   未找到包含'{job_id}'的文件")
                else:
                    debug_lines.append("   Bucket为空")
            except Exception as e:
                debug_lines.append(f"   错误: {str(e)}")
            
            # 3. 列出bucket根目录的顶层文件/文件夹
            debug_lines.append(f"\n3. Bucket根目录结构: s3://{bucket}/")
            try:
                response = self.s3.list_objects_v2(
                    Bucket=bucket,
                    Delimiter='/',
                    MaxKeys=50
                )
                
                # 列出文件夹
                if 'CommonPrefixes' in response:
                    debug_lines.append("   文件夹:")
                    for prefix_info in response['CommonPrefixes'][:20]:
                        debug_lines.append(f"   - {prefix_info['Prefix']}")
                
                # 列出文件
                if 'Contents' in response:
                    files = [obj for obj in response['Contents'] if not obj['Key'].endswith('/')]
                    if files:
                        debug_lines.append("   文件:")
                        for obj in files[:10]:
                            debug_lines.append(f"   - {obj['Key']}")
            except Exception as e:
                debug_lines.append(f"   错误: {str(e)}")
            
            return "\n".join(debug_lines)
            
        except Exception as e:
            return f"调试信息获取失败: {str(e)}"
    
    def validate_permissions(
        self, 
        role_arn: str, 
        input_bucket: str, 
        output_bucket: str
    ) -> Dict:
        """
        验证权限配置
        
        Args:
            role_arn: IAM角色ARN
            input_bucket: 输入bucket
            output_bucket: 输出bucket
            
        Returns:
            验证结果
        """
        results = {
            'valid': True,
            'checks': [],
            'errors': []
        }
        
        try:
            # 检查当前身份
            identity = self.sts.get_caller_identity()
            results['checks'].append(f"✓ 当前身份: {identity['Arn']}")
            
            # 检查输入bucket访问权限
            try:
                self.s3.head_bucket(Bucket=input_bucket)
                results['checks'].append(f"✓ 可以访问输入bucket: {input_bucket}")
            except Exception as e:
                results['valid'] = False
                results['errors'].append(f"✗ 无法访问输入bucket: {input_bucket} - {str(e)}")
            
            # 检查输出bucket访问权限
            try:
                self.s3.head_bucket(Bucket=output_bucket)
                results['checks'].append(f"✓ 可以访问输出bucket: {output_bucket}")
            except Exception as e:
                results['valid'] = False
                results['errors'].append(f"✗ 无法访问输出bucket: {output_bucket} - {str(e)}")
            
            # 检查Role ARN格式
            if role_arn and role_arn.startswith('arn:aws:iam::'):
                results['checks'].append(f"✓ Role ARN格式正确: {role_arn}")
            else:
                results['valid'] = False
                results['errors'].append(f"✗ Role ARN格式不正确: {role_arn}")
            
        except Exception as e:
            results['valid'] = False
            results['errors'].append(f"验证过程出错: {str(e)}")
        
        return results
