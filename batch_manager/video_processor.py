"""
视频批处理模块
支持Nova模型的视频理解功能
"""
import json
import base64
import logging
import os
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Callable
from .s3_manager import S3Manager

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - [VideoProcessor] - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class VideoBatchProcessor:
    """处理视频批量推理的数据准备"""
    
    def __init__(self, s3_manager: S3Manager):
        """
        初始化视频批处理器
        
        Args:
            s3_manager: S3管理器实例
        """
        self.s3_manager = s3_manager
        self.video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv']
        self.jsonl_file = None
        self.processed_count = 0
        self.max_file_size = 20 * 1024 * 1024  # 20MB建议限制
    
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
        准备视频批量推理的数据（流式处理，避免内存溢出）
        
        Args:
            bucket_name: 输入bucket名称
            prefix: 视频路径前缀
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            model_id: 模型ID
            progress_callback: 进度回调函数
            
        Returns:
            (处理的视频数量, 临时JSONL文件名)
        """
        logger.info(f"🎬 开始准备视频批量数据")
        logger.debug(f"参数 - Bucket: {bucket_name}, Prefix: {prefix}")
        logger.debug(f"参数 - Model ID: {model_id}")
        logger.debug(f"System Prompt: {system_prompt[:100]}..." if system_prompt and len(system_prompt) > 100 else f"System Prompt: {system_prompt}")
        logger.debug(f"User Prompt: {user_prompt[:100]}..." if len(user_prompt) > 100 else f"User Prompt: {user_prompt}")
        
        file_handle = None
        try:
            # 步骤1: 扫描视频文件
            logger.debug(f"步骤1: 扫描S3视频文件...")
            if progress_callback:
                progress_callback('scan', 0, 0, '正在扫描S3视频文件...')
            
            files = self.s3_manager.list_files(bucket_name, prefix)
            
            if not files:
                raise Exception(f"在 {bucket_name}/{prefix} 中未找到任何文件")
            
            # 过滤出视频文件
            video_files = [
                f for f in files
                if any(f['file_name'].lower().endswith(ext) for ext in self.video_extensions)
            ]
            
            if not video_files:
                raise Exception(f"在 {bucket_name}/{prefix} 中未找到任何视频文件")
            
            # 检查文件大小并警告
            oversized_files = []
            for file_info in video_files:
                if file_info['size'] > self.max_file_size:
                    oversized_files.append({
                        'name': file_info['file_name'],
                        'size': file_info['size']
                    })
            
            if oversized_files:
                logger.warning(f"⚠️ 发现 {len(oversized_files)} 个超过20MB的视频文件")
                for f in oversized_files:
                    logger.warning(f"  - {f['name']}: {self._format_file_size(f['size'])}")
                logger.warning("Base64编码后可能超过25MB限制，建议压缩视频或跳过这些文件")
            
            total_files = len(video_files)
            logger.info(f"✅ 发现 {total_files} 个视频文件待处理")
            logger.debug(f"支持的视频格式: {', '.join(self.video_extensions)}")
            if progress_callback:
                progress_callback('scan', total_files, total_files, f'发现 {total_files} 个视频文件待处理')
            
            # 步骤2: 创建JSONL文件并打开文件句柄
            logger.debug(f"步骤2: 创建JSONL文件...")
            timestamp = int(datetime.now().timestamp())
            filename = f'batch-video-{timestamp}.jsonl'
            file_handle = open(filename, 'w', encoding='utf-8')
            self.processed_count = 0
            logger.debug(f"JSONL文件已创建: {filename}")
            
            # 步骤3: 流式处理每个视频，即时写入JSONL文件
            logger.debug(f"步骤3: 开始逐个处理视频...")
            for idx, file_info in enumerate(video_files, 1):
                file_path = file_info['file_path']
                file_name = file_info['file_name']
                file_size = file_info['size']
                
                size_str = self._format_file_size(file_size)
                logger.debug(f"处理视频 [{idx}/{total_files}]: {file_name} ({size_str})")
                
                if progress_callback:
                    progress_callback('process', idx, total_files,
                                    f'正在处理视频: {file_name} ({size_str})')
                
                # 下载并编码视频
                video_data = self.s3_manager.read_binary_file(bucket_name, file_path)
                base64_video = base64.b64encode(video_data).decode('utf-8')
                base64_size = len(base64_video)
                logger.debug(f"视频数据大小: {file_size} bytes, Base64编码后: {base64_size} 字符")
                
                # 检查Base64大小
                if base64_size > 25 * 1024 * 1024:  # 25MB
                    logger.warning(f"⚠️ {file_name} Base64编码后超过25MB限制，跳过此文件")
                    if progress_callback:
                        progress_callback('process', idx, total_files,
                                        f'跳过超大文件: {file_name}')
                    continue
                
                # 生成模型输入（使用Nova原生格式）
                model_input = self._create_model_input(
                    system_prompt, user_prompt, base64_video, 
                    self.processed_count, file_name
                )
                
                # 立即写入JSONL文件（流式处理）
                self._write_single_record(file_handle, model_input)
                self.processed_count += 1
                logger.debug(f"✓ 视频处理完成: {file_name}, Record ID: {model_input['recordId']}")
                
                if progress_callback:
                    progress_callback('process', idx, total_files,
                                    f'已完成: {file_name} ({size_str})')
            
            logger.info(f"✅ 所有视频处理完成，共生成 {self.processed_count} 条记录")
            
            # 步骤4: 关闭文件句柄
            if file_handle:
                file_handle.close()
                file_handle = None
            
            logger.debug(f"步骤4: JSONL文件已关闭")
            file_size = os.path.getsize(filename)
            logger.info(f"✅ JSONL文件生成成功: {filename}, 大小: {file_size} bytes")
            
            if progress_callback:
                progress_callback('generate', 1, 1, f'✅ JSONL文件生成完成: {filename}（共{self.processed_count}条记录）')
            
            return self.processed_count, filename
            
        except Exception as e:
            logger.error(f"❌ 准备视频批量数据失败: {str(e)}", exc_info=True)
            # 确保文件句柄被关闭
            if file_handle:
                file_handle.close()
                file_handle = None
            
            if progress_callback:
                progress_callback('error', 0, 0, f'处理失败: {str(e)}')
            raise Exception(f"准备视频批量数据失败: {str(e)}")
    
    def _create_model_input(
        self,
        system_prompt: str,
        user_prompt: str,
        base64_video: str,
        index: int,
        file_name: str
    ) -> Dict:
        """
        创建模型输入数据（Nova原生格式）
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            base64_video: Base64编码的视频
            index: 索引
            file_name: 文件名（用于确定格式）
            
        Returns:
            模型输入字典
        """
        record_id = f"{int(datetime.now().timestamp())}_{index}"
        
        # 确定视频格式
        video_format = "mp4"  # 默认
        file_ext = file_name.lower().split('.')[-1]
        if file_ext in ['mp4', 'mov', 'avi', 'mkv', 'webm', 'flv']:
            video_format = file_ext
        
        # 构建Nova原生格式
        messages = [{
            "role": "user",
            "content": [
                {
                    "video": {
                        "format": video_format,
                        "source": {
                            "bytes": base64_video
                        }
                    }
                },
                {
                    "text": user_prompt
                }
            ]
        }]
        
        # 构建system列表（Nova要求至少有一个system消息）
        system_list = []
        if system_prompt:
            system_list.append({"text": system_prompt})
        else:
            # 如果用户未提供system prompt，使用默认值
            system_list.append({"text": "你是一个专业的视频分析助手。"})
        
        # 配置推理参数
        inference_config = {
            "maxTokens": 300,
            "topP": 0.1,
            "topK": 20,
            "temperature": 0.3
        }
        
        # 返回Nova原生格式
        return {
            "recordId": record_id,
            "modelInput": {
                "schemaVersion": "messages-v1",
                "messages": messages,
                "system": system_list,
                "inferenceConfig": inference_config
            }
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
    
    @staticmethod
    def _format_file_size(size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        else:
            return f"{size / (1024 * 1024):.1f}MB"
