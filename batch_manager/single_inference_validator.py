"""
单次推理验证模块
用于在批处理前验证prompt组装和模型调用的正确性
"""
import boto3
import json
import random
import base64
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime
from .s3_manager import S3Manager

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - [SingleInferenceValidator] - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class SingleInferenceValidator:
    """单次推理验证器"""
    
    def __init__(self, bedrock_region: str, s3_manager: S3Manager):
        """
        初始化验证器
        
        Args:
            bedrock_region: Bedrock服务所在区域
            s3_manager: S3管理器实例
        """
        self.bedrock_runtime = boto3.client('bedrock-runtime', region_name=bedrock_region)
        self.s3_manager = s3_manager
        self.bedrock_region = bedrock_region
    
    def validate_text_inference(
        self,
        use_jsonl: bool,
        input_bucket: str,
        input_prefix: str,
        jsonl_s3_uri: str,
        prompt: str,
        model_id: str
    ) -> Dict:
        """
        验证文本批处理的单次推理
        
        Args:
            use_jsonl: 是否使用JSONL文件模式
            input_bucket: 输入bucket（原始文件模式）
            input_prefix: 输入路径前缀（原始文件模式）
            jsonl_s3_uri: JSONL文件URI（JSONL模式）
            prompt: 提示词
            model_id: 模型ID
            
        Returns:
            验证结果字典
        """
        logger.info("🧪 开始文本推理验证...")
        try:
            if use_jsonl:
                # JSONL模式：读取第一个item
                logger.debug("JSONL模式：读取第一个item")
                model_input, file_info = self._get_first_jsonl_item(jsonl_s3_uri)
                
                # 检查JSONL格式是否与当前模型匹配
                is_nova_model = 'nova' in model_id.lower()
                is_nova_format = 'schemaVersion' in model_input and 'inferenceConfig' in model_input
                is_claude_format = 'anthropic_version' in model_input and 'max_tokens' in model_input
                
                if is_nova_model and is_claude_format:
                    logger.warning("⚠️ JSONL文件为Claude格式，但选择了Nova模型")
                    return self._error_result(
                        "JSONL文件格式不匹配：文件是为Claude模型生成的（包含max_tokens），"
                        "但您选择了Nova模型。请使用匹配的模型或重新生成JSONL文件。"
                    )
                elif not is_nova_model and is_nova_format:
                    logger.warning("⚠️ JSONL文件为Nova格式，但选择了Claude模型")
                    return self._error_result(
                        "JSONL文件格式不匹配：文件是为Nova模型生成的（包含inferenceConfig），"
                        "但您选择了Claude模型。请使用匹配的模型或重新生成JSONL文件。"
                    )
                
                logger.debug(f"JSONL格式检查通过 - Nova模型: {is_nova_model}, Nova格式: {is_nova_format}, Claude格式: {is_claude_format}")
            else:
                # 原始文件模式：随机选择一个txt文件
                logger.debug("原始文件模式：随机选择txt文件")
                files = self.s3_manager.list_files(input_bucket, input_prefix)
                txt_files = [f for f in files if f['file_name'].lower().endswith('.txt')]
                
                if not txt_files:
                    return self._error_result("未找到任何.txt文件")
                
                # 随机选择一个文件
                selected_file = random.choice(txt_files)
                file_info = f"文件: {selected_file['file_name']} ({selected_file['size']} bytes)"
                logger.info(f"选中文件: {selected_file['file_name']}")
                
                # 读取文件内容
                content = self.s3_manager.read_file(input_bucket, selected_file['file_path'])
                
                # 根据模型类型组装不同格式的输入
                if 'nova' in model_id.lower():
                    # Nova模型使用原生API格式
                    model_input = {
                        "schemaVersion": "messages-v1",
                        "messages": [{
                            "role": "user",
                            "content": [{"text": f"{prompt}\n\n{content}"}]
                        }],
                        "inferenceConfig": {
                            "maxTokens": 2048,
                            "temperature": 0.1,
                            "topP": 0.9
                        }
                    }
                else:
                    # Claude模型使用Messages API格式
                    model_input = {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 2048,
                        "temperature": 0.1,
                        "messages": [{
                            "role": "user",
                            "content": f"{prompt}\n\n{content}"
                        }]
                    }
            
            # 调用模型
            logger.debug("调用Bedrock Runtime进行推理...")
            start_time = datetime.now()
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(model_input)
            )
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 解析响应（根据模型类型使用不同格式）
            response_body = json.loads(response['body'].read())
            
            if 'nova' in model_id.lower():
                # Nova模型响应格式
                output_text = response_body['output']['message']['content'][0]['text']
                stop_reason = response_body['output'].get('stopReason', 'unknown')
                input_tokens = response_body.get('usage', {}).get('inputTokens', 0)
                output_tokens = response_body.get('usage', {}).get('outputTokens', 0)
            else:
                # Claude模型响应格式
                output_text = response_body['content'][0]['text']
                stop_reason = response_body.get('stop_reason', 'unknown')
                input_tokens = response_body.get('usage', {}).get('input_tokens', 0)
                output_tokens = response_body.get('usage', {}).get('output_tokens', 0)
            
            logger.info(f"✅ 推理成功！耗时: {duration:.2f}秒, 输入tokens: {input_tokens}, 输出tokens: {output_tokens}")
            
            return self._success_result(
                file_info=file_info,
                prompt=prompt if not use_jsonl else "来自JSONL文件",
                output_text=output_text,
                stop_reason=stop_reason,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration=duration,
                model_input=model_input
            )
            
        except Exception as e:
            logger.error(f"❌ 验证失败: {str(e)}", exc_info=True)
            return self._error_result(str(e))
    
    def validate_image_inference(
        self,
        use_jsonl: bool,
        input_bucket: str,
        input_prefix: str,
        jsonl_s3_uri: str,
        system_prompt: str,
        user_prompt: str,
        model_id: str
    ) -> Dict:
        """验证图片批处理的单次推理"""
        logger.info("🧪 开始图片推理验证...")
        try:
            if use_jsonl:
                # JSONL模式：读取第一个item
                logger.debug("JSONL模式：读取第一个item")
                model_input, file_info = self._get_first_jsonl_item(jsonl_s3_uri)
                
                # 检查JSONL格式是否与当前模型匹配
                is_nova_model = 'nova' in model_id.lower()
                is_nova_format = 'schemaVersion' in model_input and 'inferenceConfig' in model_input
                is_claude_format = 'anthropic_version' in model_input and 'max_tokens' in model_input
                
                if is_nova_model and is_claude_format:
                    logger.warning("⚠️ JSONL文件为Claude格式，但选择了Nova模型")
                    return self._error_result(
                        "JSONL文件格式不匹配：文件是为Claude模型生成的（包含max_tokens），"
                        "但您选择了Nova模型。请使用匹配的模型或重新生成JSONL文件。"
                    )
                elif not is_nova_model and is_nova_format:
                    logger.warning("⚠️ JSONL文件为Nova格式，但选择了Claude模型")
                    return self._error_result(
                        "JSONL文件格式不匹配：文件是为Nova模型生成的（包含inferenceConfig），"
                        "但您选择了Claude模型。请使用匹配的模型或重新生成JSONL文件。"
                    )
                
                logger.debug(f"JSONL格式检查通过 - Nova模型: {is_nova_model}, Nova格式: {is_nova_format}, Claude格式: {is_claude_format}")
            else:
                # 原始文件模式：随机选择一个图片
                files = self.s3_manager.list_files(input_bucket, input_prefix)
                image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
                image_files = [f for f in files if any(f['file_name'].lower().endswith(ext) for ext in image_extensions)]
                
                if not image_files:
                    return self._error_result("未找到任何图片文件")
                
                selected_file = random.choice(image_files)
                file_info = f"文件: {selected_file['file_name']} ({selected_file['size']} bytes)"
                logger.info(f"选中文件: {selected_file['file_name']}")
                
                # 读取并编码图片
                image_data = self.s3_manager.read_binary_file(input_bucket, selected_file['file_path'])
                base64_image = base64.b64encode(image_data).decode('utf-8')
                
                # 确定图片格式
                image_format = selected_file['file_name'].lower().split('.')[-1]
                if image_format == 'jpg':
                    image_format = 'jpeg'
                
                # 根据模型类型组装不同格式
                if 'nova' in model_id.lower():
                    # Nova模型使用原生API格式
                    content = [
                        {
                            "image": {
                                "format": image_format,
                                "source": {"bytes": base64_image}
                            }
                        }
                    ]
                    if user_prompt:
                        content.append({"text": user_prompt})
                    
                    messages = [{"role": "user", "content": content}]
                    
                    system_list = []
                    if system_prompt:
                        system_list.append({"text": system_prompt})
                    
                    model_input = {
                        "schemaVersion": "messages-v1",
                        "messages": messages,
                        "inferenceConfig": {
                            "maxTokens": 300,
                            "temperature": 0.1,
                            "topP": 0.9
                        }
                    }
                    if system_list:
                        model_input["system"] = system_list
                else:
                    # Claude模型使用Messages API格式
                    content = [{
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": f"image/{image_format}",
                            "data": base64_image
                        }
                    }]
                    
                    if user_prompt:
                        content.append({"type": "text", "text": user_prompt})
                    
                    messages = [{"role": "user", "content": content}]
                    
                    model_input = {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 300,
                        "temperature": 0.1
                    }
                    
                    if system_prompt:
                        model_input["system"] = system_prompt
                    
                    model_input["messages"] = messages
            
            # 调用模型
            start_time = datetime.now()
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(model_input)
            )
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 解析响应（根据模型类型使用不同格式）
            response_body = json.loads(response['body'].read())
            
            if 'nova' in model_id.lower():
                # Nova模型响应格式
                output_text = response_body['output']['message']['content'][0]['text']
                stop_reason = response_body['output'].get('stopReason', 'unknown')
                input_tokens = response_body.get('usage', {}).get('inputTokens', 0)
                output_tokens = response_body.get('usage', {}).get('outputTokens', 0)
            else:
                # Claude模型响应格式
                output_text = response_body['content'][0]['text']
                stop_reason = response_body.get('stop_reason', 'unknown')
                input_tokens = response_body.get('usage', {}).get('input_tokens', 0)
                output_tokens = response_body.get('usage', {}).get('output_tokens', 0)
            
            logger.info(f"✅ 推理成功！耗时: {duration:.2f}秒")
            
            return self._success_result(
                file_info=file_info,
                prompt=f"System: {system_prompt}\nUser: {user_prompt}" if not use_jsonl else "来自JSONL文件",
                output_text=output_text,
                stop_reason=stop_reason,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration=duration,
                model_input=model_input
            )
            
        except Exception as e:
            logger.error(f"❌ 验证失败: {str(e)}", exc_info=True)
            return self._error_result(str(e))
    
    def validate_video_inference(
        self,
        use_jsonl: bool,
        input_bucket: str,
        input_prefix: str,
        jsonl_s3_uri: str,
        system_prompt: str,
        user_prompt: str,
        model_id: str
    ) -> Dict:
        """验证视频批处理的单次推理"""
        logger.info("🧪 开始视频推理验证...")
        try:
            if use_jsonl:
                # JSONL模式
                model_input, file_info = self._get_first_jsonl_item(jsonl_s3_uri)
            else:
                # 原始文件模式：随机选择一个视频
                files = self.s3_manager.list_files(input_bucket, input_prefix)
                video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv']
                video_files = [f for f in files if any(f['file_name'].lower().endswith(ext) for ext in video_extensions)]
                
                if not video_files:
                    return self._error_result("未找到任何视频文件")
                
                selected_file = random.choice(video_files)
                file_info = f"文件: {selected_file['file_name']} ({selected_file['size']} bytes)"
                logger.info(f"选中文件: {selected_file['file_name']}")
                
                # 读取并编码视频
                video_data = self.s3_manager.read_binary_file(input_bucket, selected_file['file_path'])
                base64_video = base64.b64encode(video_data).decode('utf-8')
                
                # 确定视频格式
                video_format = selected_file['file_name'].lower().split('.')[-1]
                
                # 组装Nova格式
                messages = [{
                    "role": "user",
                    "content": [
                        {
                            "video": {
                                "format": video_format,
                                "source": {"bytes": base64_video}
                            }
                        },
                        {"text": user_prompt}
                    ]
                }]
                
                system_list = []
                if system_prompt:
                    system_list.append({"text": system_prompt})
                else:
                    system_list.append({"text": "你是一个专业的视频分析助手。"})
                
                model_input = {
                    "schemaVersion": "messages-v1",
                    "messages": messages,
                    "system": system_list,
                    "inferenceConfig": {
                        "maxTokens": 300,
                        "topP": 0.1,
                        "topK": 20,
                        "temperature": 0.3
                    }
                }
            
            # 调用模型
            start_time = datetime.now()
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(model_input)
            )
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 解析响应（Nova格式）
            response_body = json.loads(response['body'].read())
            output_text = response_body['output']['message']['content'][0]['text']
            stop_reason = response_body['output'].get('stopReason', 'unknown')
            input_tokens = response_body.get('usage', {}).get('inputTokens', 0)
            output_tokens = response_body.get('usage', {}).get('outputTokens', 0)
            
            logger.info(f"✅ 推理成功！耗时: {duration:.2f}秒")
            
            return self._success_result(
                file_info=file_info,
                prompt=f"System: {system_prompt}\nUser: {user_prompt}" if not use_jsonl else "来自JSONL文件",
                output_text=output_text,
                stop_reason=stop_reason,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration=duration,
                model_input=model_input
            )
            
        except Exception as e:
            logger.error(f"❌ 验证失败: {str(e)}", exc_info=True)
            return self._error_result(str(e))
    
    def _get_first_jsonl_item(self, jsonl_s3_uri: str) -> Tuple[Dict, str]:
        """
        从JSONL文件读取第一个item
        
        Returns:
            (model_input, file_info)
        """
        # 解析S3 URI
        s3_path = jsonl_s3_uri.replace('s3://', '')
        parts = s3_path.split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ''
        
        logger.debug(f"读取JSONL文件: s3://{bucket}/{key}")
        
        # 读取文件内容
        file_response = self.s3_manager.s3.get_object(Bucket=bucket, Key=key)
        content = file_response['Body'].read().decode('utf-8')
        
        # 获取第一行
        first_line = content.strip().split('\n')[0]
        item = json.loads(first_line)
        
        # 提取modelInput
        model_input = item.get('modelInput', {})
        record_id = item.get('recordId', 'unknown')
        
        file_info = f"JSONL Record ID: {record_id}"
        logger.debug(f"已读取JSONL第一个item: {record_id}")
        
        return model_input, file_info
    
    def _success_result(
        self,
        file_info: str,
        prompt: str,
        output_text: str,
        stop_reason: str,
        input_tokens: int,
        output_tokens: int,
        duration: float,
        model_input: Dict
    ) -> Dict:
        """构建成功结果"""
        return {
            'success': True,
            'file_info': file_info,
            'prompt': prompt,
            'output_text': output_text,
            'stop_reason': stop_reason,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'duration': duration,
            'model_input_preview': json.dumps(model_input, ensure_ascii=False, indent=2)[:500] + '...'
        }
    
    def _error_result(self, error_message: str) -> Dict:
        """构建错误结果"""
        return {
            'success': False,
            'error': error_message
        }
