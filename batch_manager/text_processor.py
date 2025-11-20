"""
文本批处理模块
"""
import json
import os
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
    formatter = logging.Formatter('%(asctime)s - [TextProcessor] - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class TextBatchProcessor:
    """处理文本批量推理的数据准备"""
    
    def __init__(self, s3_manager: S3Manager):
        """
        初始化文本批处理器
        
        Args:
            s3_manager: S3管理器实例
        """
        self.s3_manager = s3_manager
    
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
        准备文本批量推理的数据
        
        Args:
            bucket_name: 输入bucket名称
            prefix: 文件路径前缀
            prompt: 用户提供的prompt提示词
            model_id: 模型ID
            max_tokens: 最大token数
            temperature: 温度参数
            progress_callback: 进度回调函数
            
        Returns:
            (model_inputs列表, 临时JSONL文件名)
        """
        logger.info(f"📝 开始准备文本批量数据")
        logger.debug(f"参数 - Bucket: {bucket_name}, Prefix: {prefix}")
        logger.debug(f"参数 - Model ID: {model_id}, Max Tokens: {max_tokens}, Temperature: {temperature}")
        logger.debug(f"Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"Prompt: {prompt}")
        try:
            # 步骤1: 扫描文件
            logger.debug(f"步骤1: 扫描S3输入文件...")
            if progress_callback:
                progress_callback('scan', 0, 0, '正在扫描输入文件...')
            
            all_files = self.s3_manager.list_files(bucket_name, prefix)
            
            if not all_files:
                raise Exception(f"在 {bucket_name}/{prefix} 中未找到任何文件")
            
            # 只处理.txt文件
            files = [f for f in all_files if f['file_name'].lower().endswith('.txt')]
            
            if not files:
                logger.warning(f"在 {len(all_files)} 个文件中未找到.txt文件")
                raise Exception(f"在 {bucket_name}/{prefix} 中未找到任何.txt文件（共{len(all_files)}个文件）")
            
            total_files = len(files)
            logger.info(f"✅ 发现 {total_files} 个.txt文件待处理（共扫描{len(all_files)}个文件）")
            if progress_callback:
                progress_callback('scan', total_files, total_files, 
                                f'发现 {total_files} 个.txt文件待处理（共扫描{len(all_files)}个文件）')
            
            model_inputs = []
            
            # 步骤2: 处理每个文件
            logger.debug(f"步骤2: 开始逐个处理文件...")
            for idx, file_info in enumerate(files, 1):
                file_path = file_info['file_path']
                file_name = file_info['file_name']
                file_size = file_info['size']
                
                size_str = self._format_file_size(file_size)
                logger.debug(f"处理文件 [{idx}/{total_files}]: {file_name} ({size_str})")
                
                if progress_callback:
                    progress_callback('process', idx, total_files,
                                    f'正在处理: {file_name} ({size_str})')
                
                # 读取文件内容
                file_content = self.s3_manager.read_file(bucket_name, file_path)
                logger.debug(f"文件内容长度: {len(file_content)} 字符")
                
                # 生成模型输入
                model_input = self._create_model_input(
                    prompt, file_content, len(model_inputs),
                    max_tokens, temperature, model_id
                )
                model_inputs.append(model_input)
                logger.debug(f"✓ 文件处理完成: {file_name}, Record ID: {model_input['recordId']}")
                
                if progress_callback:
                    progress_callback('process', idx, total_files,
                                    f'已完成: {file_name} ({size_str})')
            
            logger.info(f"✅ 所有文件处理完成，共生成 {len(model_inputs)} 条记录")
            
            # 步骤3: 生成JSONL文件
            logger.debug(f"步骤3: 生成JSONL文件...")
            if progress_callback:
                progress_callback('generate', 0, 1, '正在生成批处理JSONL文件...')
            
            filename = self._write_jsonl_file(model_inputs)
            logger.info(f"✅ JSONL文件生成成功: {filename}, 大小: {os.path.getsize(filename)} bytes")
            
            if progress_callback:
                progress_callback('generate', 1, 1, f'JSONL文件生成完成: {filename}')
            
            return model_inputs, filename
            
        except Exception as e:
            logger.error(f"❌ 准备批量数据失败: {str(e)}", exc_info=True)
            if progress_callback:
                progress_callback('error', 0, 0, f'处理失败: {str(e)}')
            raise Exception(f"准备批量数据失败: {str(e)}")
    
    def _create_model_input(
        self,
        prompt: str,
        file_content: str,
        index: int,
        max_tokens: int,
        temperature: float,
        model_id: str
    ) -> Dict:
        """
        创建模型输入数据
        
        Args:
            prompt: 提示词
            file_content: 文件内容
            index: 索引
            max_tokens: 最大token数
            temperature: 温度参数
            model_id: 模型ID
            
        Returns:
            模型输入字典
        """
        record_id = f"{int(datetime.now().timestamp())}_{index}"
        input_text = f"{prompt}\n\n原始文本:\n{file_content}"
        
        # 根据模型类型生成不同格式
        if 'nova' in model_id.lower():
            # Nova模型使用原生API格式
            body = {
                "schemaVersion": "messages-v1",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": input_text
                            }
                        ]
                    }
                ],
                "inferenceConfig": {
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                    "topP": 0.9
                }
            }
        else:
            # Claude模型使用Messages API格式
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
        
        return {
            "recordId": record_id,
            "modelInput": body
        }
    
    def _write_jsonl_file(self, model_inputs: List[Dict]) -> str:
        """
        写入JSONL文件
        
        Args:
            model_inputs: 模型输入列表
            
        Returns:
            文件名
        """
        timestamp = int(datetime.now().timestamp())
        filename = f'batch-{timestamp}.jsonl'
        
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
