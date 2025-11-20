"""
AWS Bedrock Batch Inference Manager
处理批量推理任务的创建、监控和结果获取
支持文本和图片两种批处理模式

此文件为向后兼容层，实际实现已重构为模块化结构
位于 batch_manager/ 目录下
"""

# 从新的模块化结构中导入
from batch_manager import BatchInferenceManager

__all__ = ['BatchInferenceManager']

# 保持向后兼容 - 如果有代码直接 from batch_manager import BatchInferenceManager
# 仍然可以正常工作
