"""
图片批处理模块
"""
import json
import base64
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Callable
from .s3_manager import S3Manager

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - [ImageProcessor] - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class ImageBatchProcessor:
    """处理图片批量推理的数据准备"""
    
    def __init__(self, s3_manager: S3Manager):
        """
        初始化图片批处理器
        
        Args:
            s3_manager: S3管理器实例
        """
        self.s3_manager = s3_manager
        self.image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        self.jsonl_file = None
        self.processed_count = 0
    
    def prepare_batch_data(
        self,
        bucket_name: str,
        prefix: str,
        system_prompt: str,
        user_prompt: str,
        model_id: str,
        progress_callback: Optional[Callable] = None
    ) -> Tuple[int, str]:
        """
        准备图片批量推理的数据（流式处理，避免内存溢出）
        
        Args:
            bucket_name: 输入bucket名称
            prefix: 图片路径前缀
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            model_id: 模型ID
            progress_callback: 进度回调函数
            
        Returns:
            (处理的图片数量, 临时JSONL文件名)
        """
        logger.info(f"🖼️ 开始准备图片批量数据")
        logger.debug(f"参数 - Bucket: {bucket_name}, Prefix: {prefix}")
        logger.debug(f"参数 - Model ID: {model_id}")
        logger.debug(f"System Prompt: {system_prompt[:100]}..." if system_prompt and len(system_prompt) > 100 else f"System Prompt: {system_prompt}")
        logger.debug(f"User Prompt: {user_prompt[:100]}..." if len(user_prompt) > 100 else f"User Prompt: {user_prompt}")
        
        file_handle = None
        try:
            # 步骤1: 扫描图片文件
            logger.debug(f"步骤1: 扫描S3图片文件...")
            if progress_callback:
                progress_callback('scan', 0, 0, '正在扫描S3图片文件...')
            
            files = self.s3_manager.list_files(bucket_name, prefix)
            
            if not files:
                raise Exception(f"在 {bucket_name}/{prefix} 中未找到任何文件")
            
            # 过滤出图片文件
            image_files = [
                f for f in files
                if any(f['file_name'].lower().endswith(ext) for ext in self.image_extensions)
            ]
            
            if not image_files:
                raise Exception(f"在 {bucket_name}/{prefix} 中未找到任何图片文件")
            
            total_files = len(image_files)
            logger.info(f"✅ 发现 {total_files} 个图片文件待处理")
            logger.debug(f"支持的图片格式: {', '.join(self.image_extensions)}")
            if progress_callback:
                progress_callback('scan', total_files, total_files, f'发现 {total_files} 个图片文件待处理')
            
            # 步骤2: 创建JSONL文件并打开文件句柄
            logger.debug(f"步骤2: 创建JSONL文件...")
            timestamp = int(datetime.now().timestamp())
            filename = f'batch-image-{timestamp}.jsonl'
            file_handle = open(filename, 'w', encoding='utf-8')
            self.processed_count = 0
            logger.debug(f"JSONL文件已创建: {filename}")
            
            # 步骤3: 流式处理每个图片，即时写入JSONL文件
            logger.debug(f"步骤3: 开始逐个处理图片...")
            skipped_files = []
            
            for idx, file_info in enumerate(image_files, 1):
                file_path = file_info['file_path']
                file_name = file_info['file_name']
                file_size = file_info['size']
                
                size_str = self._format_file_size(file_size)
                logger.debug(f"处理图片 [{idx}/{total_files}]: {file_name} ({size_str})")
                
                if progress_callback:
                    progress_callback('process', idx, total_files,
                                    f'正在处理图片: {file_name} ({size_str})')
                
                try:
                    # 下载并编码图片
                    image_data = self.s3_manager.read_binary_file(bucket_name, file_path)
                    base64_image = base64.b64encode(image_data).decode('utf-8')
                    base64_size = len(base64_image)
                    logger.debug(f"图片数据大小: {file_size} bytes, Base64编码后: {base64_size} 字符")
                    
                    # 检查payload大小（Base64编码后不应超过约25MB，留一些余量用于其他字段）
                    max_payload_size = 20 * 1024 * 1024  # 20MB限制
                    if base64_size > max_payload_size:
                        error_msg = f"Base64编码后大小 {base64_size} 字符超过限制 {max_payload_size}"
                        logger.warning(f"⚠️ 跳过图片 {file_name}: {error_msg}")
                        skipped_files.append({'file': file_name, 'reason': error_msg})
                        continue
                    
                    # 生成模型输入
                    model_input = self._create_model_input(
                        system_prompt, user_prompt, base64_image, self.processed_count, model_id
                    )
                    
                    # 立即写入JSONL文件（流式处理）
                    self._write_single_record(file_handle, model_input)
                    self.processed_count += 1
                    logger.debug(f"✓ 图片处理完成: {file_name}, Record ID: {model_input['recordId']}")
                    
                    if progress_callback:
                        progress_callback('process', idx, total_files,
                                        f'已完成: {file_name} ({size_str})')
                
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"❌ 处理图片失败 {file_name}: {error_msg}")
                    skipped_files.append({'file': file_name, 'reason': error_msg})
                    # 继续处理下一个图片
                    continue
            
            # 输出处理总结
            if skipped_files:
                logger.warning(f"⚠️ 有 {len(skipped_files)} 个图片被跳过:")
                for skipped in skipped_files:
                    logger.warning(f"  - {skipped['file']}: {skipped['reason']}")
            
            logger.info(f"✅ 所有图片处理完成，共生成 {self.processed_count} 条记录，跳过 {len(skipped_files)} 个")
            
            # 步骤4: 关闭文件句柄
            if file_handle:
                file_handle.close()
                file_handle = None
            
            logger.debug(f"步骤4: JSONL文件已关闭")
            import os
            file_size = os.path.getsize(filename)
            logger.info(f"✅ JSONL文件生成成功: {filename}, 大小: {file_size} bytes")
            
            if progress_callback:
                progress_callback('generate', 1, 1, f'✅ JSONL文件生成完成: {filename}（共{self.processed_count}条记录）')
            
            return self.processed_count, filename
            
        except Exception as e:
            logger.error(f"❌ 准备图片批量数据失败: {str(e)}", exc_info=True)
            # 确保文件句柄被关闭
            if file_handle:
                file_handle.close()
                file_handle = None
            
            if progress_callback:
                progress_callback('error', 0, 0, f'处理失败: {str(e)}')
            raise Exception(f"准备图片批量数据失败: {str(e)}")
    
    def _create_model_input(
        self,
        system_prompt: str,
        user_prompt: str,
        base64_image: str,
        index: int,
        model_id: str
    ) -> Dict:
        """
        创建模型输入数据
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            base64_image: Base64编码的图片
            index: 索引
            model_id: 模型ID
            
        Returns:
            模型输入字典
        """
        record_id = f"{int(datetime.now().timestamp())}_{index}"
        
        # 根据模型类型生成不同格式
        if 'nova' in model_id.lower():
            # Nova模型使用原生API格式
            content = [
                {
                    "image": {
                        "format": "jpeg",
                        "source": {"bytes": base64_image}
                    }
                },
                {"text": user_prompt}
            ]
            
            body = {
                "schemaVersion": "messages-v1",
                "messages": [{
                    "role": "user",
                    "content": content
                }],
                "inferenceConfig": {
                    "maxTokens": 300,
                    "temperature": 0.1,
                    "topP": 0.9
                }
            }
            
            # 添加system prompt（如果有）
            if system_prompt:
                body["system"] = [{"text": system_prompt}]
        else:
            # Claude模型使用Messages API格式
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "temperature": 0.1,
                "top_p": 0.1,
                "top_k": 100,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": base64_image
                                }
                            },
                            {
                                "type": "text",
                                "text": user_prompt
                            }
                        ]
                    }
                ]
            }
            
            # 如果有system prompt，添加到body中
            if system_prompt:
                body["system"] = system_prompt
        
        return {
            "recordId": record_id,
            "modelInput": body
        }
    
    def _write_single_record(self, file_handle, record: Dict) -> None:
        """
        将单条记录写入JSONL文件并立即刷新
        
        Args:
            file_handle: 已打开的文件句柄
            record: 要写入的单条记录字典
        """
        json_str = json.dumps(record, ensure_ascii=False)
        file_handle.write(json_str + '\n')
        file_handle.flush()  # 立即刷新到磁盘，避免数据丢失
    
    def _write_jsonl_file(self, model_inputs: List[Dict]) -> str:
        """
        写入JSONL文件
        
        Args:
            model_inputs: 模型输入列表
            
        Returns:
            文件名
        """
        timestamp = int(datetime.now().timestamp())
        filename = f'batch-image-{timestamp}.jsonl'
        
        with open(filename, 'w', encoding='utf-8') as f:
            for item in model_inputs:
                json_str = json.dumps(item, ensure_ascii=False)
                f.write(json_str + '\n')
        
        return filename
    
    @staticmethod
    def _format_file_size(size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        else:
            return f"{size / (1024 * 1024):.1f}MB"
