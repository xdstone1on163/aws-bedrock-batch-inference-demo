"""
AWS Bedrock Batch Inference Manager
批量推理管理器包

重构后的模块化结构：
- s3_manager: S3操作管理
- text_processor: 文本批处理
- image_processor: 图片批处理  
- job_manager: 任务管理
- validator: 权限验证
- core: 核心协调器
"""

from .core import BatchInferenceManager

__all__ = ['BatchInferenceManager']
__version__ = '2.0.0'
