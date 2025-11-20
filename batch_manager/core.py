"""
核心协调器模块
BatchInferenceManager - 组合所有功能模块的主协调器
"""
import os
from typing import Dict, List, Tuple, Optional, Callable
from .s3_manager import S3Manager
from .text_processor import TextBatchProcessor
from .image_processor import ImageBatchProcessor
from .video_processor import VideoBatchProcessor
from .job_manager import JobManager
from .validator import PermissionValidator
from .single_inference_validator import SingleInferenceValidator


class BatchInferenceManager:
    """
    AWS Bedrock批量推理管理器
    整合所有功能模块，提供统一的接口
    """
    
    def __init__(self, bedrock_region: str = 'us-east-1', s3_region: str = 'us-east-1'):
        """
        初始化批量推理管理器
        
        Args:
            bedrock_region: Bedrock服务所在区域
            s3_region: S3 bucket所在区域
        """
        self.bedrock_region = bedrock_region
        self.s3_region = s3_region
        
        # 初始化各个功能模块
        self.s3_manager = S3Manager(s3_region)
        self.text_processor = TextBatchProcessor(self.s3_manager)
        self.image_processor = ImageBatchProcessor(self.s3_manager)
        self.video_processor = VideoBatchProcessor(self.s3_manager)
        self.job_manager = JobManager(bedrock_region, self.s3_manager)
        self.validator = PermissionValidator(s3_region, self.s3_manager)
        self.inference_validator = SingleInferenceValidator(bedrock_region, self.s3_manager)
        
        # 保持向后兼容的属性
        self.current_jobs = self.job_manager.current_jobs
    
    # S3相关方法
    def list_input_files(self, bucket_name: str, prefix: str) -> List[Dict]:
        """列出输入bucket中的文件"""
        return self.s3_manager.list_files(bucket_name, prefix)
    
    def read_file_content(self, bucket_name: str, file_path: str) -> str:
        """读取S3文件内容"""
        return self.s3_manager.read_file(bucket_name, file_path)
    
    def upload_to_s3(self, local_file: str, bucket_name: str, s3_key: str) -> str:
        """上传文件到S3"""
        return self.s3_manager.upload_file(local_file, bucket_name, s3_key)
    
    def upload_local_files(self, local_files: List[str], bucket_name: str, prefix: str = "raw_data") -> List[str]:
        """批量上传本地文件到S3"""
        prefix = S3Manager.normalize_prefix(prefix)
        return self.s3_manager.upload_files(local_files, bucket_name, prefix)
    
    @staticmethod
    def normalize_prefix(prefix: str) -> str:
        """规范化S3前缀"""
        return S3Manager.normalize_prefix(prefix)
    
    # 文本批处理方法
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
        """准备文本批量推理的数据"""
        return self.text_processor.prepare_batch_data(
            bucket_name, prefix, prompt, model_id,
            max_tokens, temperature, progress_callback
        )
    
    # 图片批处理方法
    def download_and_encode_image(self, bucket_name: str, image_key: str) -> str:
        """下载并编码图片（为向后兼容保留）"""
        import base64
        image_data = self.s3_manager.read_binary_file(bucket_name, image_key)
        return base64.b64encode(image_data).decode('utf-8')
    
    def prepare_image_batch_data(
        self,
        bucket_name: str,
        prefix: str,
        system_prompt: str,
        user_prompt: str,
        model_id: str,
        progress_callback: Optional[Callable] = None
    ) -> Tuple[int, str]:
        """准备图片批量推理的数据（流式处理，返回处理的图片数量和文件名）"""
        return self.image_processor.prepare_batch_data(
            bucket_name, prefix, system_prompt, user_prompt,
            model_id, progress_callback
        )
    
    # 任务管理方法
    def create_batch_job_from_jsonl(
        self,
        jsonl_s3_uri: str,
        output_bucket: str,
        output_prefix: str,
        model_id: str,
        role_arn: str,
        job_name: Optional[str] = None
    ) -> Dict:
        """使用已有的JSONL文件创建批量推理任务"""
        output_prefix = S3Manager.normalize_prefix(output_prefix)
        return self.job_manager.create_job(
            jsonl_s3_uri, output_bucket, output_prefix,
            model_id, role_arn, job_name
        )
    
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
        """创建文本批量推理任务"""
        try:
            # 如果提供了本地文件，先上传
            if local_files:
                if progress_callback:
                    progress_callback('upload', 0, len(local_files), '正在上传本地文件到S3...')
                
                raw_data_prefix = S3Manager.normalize_prefix(input_prefix) + "raw_data"
                self.upload_local_files(local_files, input_bucket, raw_data_prefix)
                input_prefix = raw_data_prefix
                
                if progress_callback:
                    progress_callback('upload', len(local_files), len(local_files),
                                    f'已上传 {len(local_files)} 个本地文件')
            
            # 规范化前缀
            input_prefix = S3Manager.normalize_prefix(input_prefix)
            output_prefix = S3Manager.normalize_prefix(output_prefix)
            
            # 准备批量数据
            model_inputs, filename = self.prepare_batch_data(
                input_bucket, input_prefix, prompt, model_id,
                progress_callback=progress_callback
            )
            
            # 上传JSONL文件到S3
            s3_key = f"{input_prefix}{filename}" if input_prefix else filename
            input_s3_uri = self.upload_to_s3(filename, input_bucket, s3_key)
            
            if progress_callback:
                progress_callback('upload', 1, 1, f'✅ JSONL文件已上传到: {input_s3_uri}')
            
            # 清理本地临时文件
            if os.path.exists(filename):
                os.remove(filename)
            
            # 创建批处理任务
            result = self.create_batch_job_from_jsonl(
                input_s3_uri, output_bucket, output_prefix,
                model_id, role_arn, job_name
            )
            
            if result['success']:
                result['message'] = f"成功提交批量推理任务，共{len(model_inputs)}个文件"
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f"创建批量任务失败: {str(e)}"
            }
    
    def create_image_batch_job(
        self,
        input_bucket: str,
        input_prefix: str,
        output_bucket: str,
        output_prefix: str,
        model_id: str,
        role_arn: str,
        system_prompt: str,
        user_prompt: str,
        job_name: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """创建图片批量推理任务"""
        try:
            # 规范化前缀
            input_prefix = S3Manager.normalize_prefix(input_prefix)
            output_prefix = S3Manager.normalize_prefix(output_prefix)
            
            # 准备图片批量数据（流式处理，返回处理数量和文件名）
            image_count, filename = self.prepare_image_batch_data(
                input_bucket, input_prefix, system_prompt,
                user_prompt, model_id, progress_callback
            )
            
            # 上传JSONL文件到S3
            s3_key = f"{input_prefix}{filename}" if input_prefix else filename
            input_s3_uri = self.upload_to_s3(filename, input_bucket, s3_key)
            
            if progress_callback:
                progress_callback('upload', 1, 1, f'✅ JSONL文件已上传到: {input_s3_uri}')
            
            # 清理本地临时文件
            if os.path.exists(filename):
                os.remove(filename)
            
            # 创建批处理任务
            result = self.create_batch_job_from_jsonl(
                input_s3_uri, output_bucket, output_prefix,
                model_id, role_arn, job_name
            )
            
            if result['success']:
                result['message'] = f"成功提交图片批量推理任务，共{image_count}个图片"
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f"创建图片批量任务失败: {str(e)}"
            }
    
    def get_job_status(self, job_arn: str) -> Dict:
        """获取任务状态"""
        return self.job_manager.get_job_status(job_arn)
    
    def monitor_job(self, job_arn: str, check_interval: int = 30) -> Dict:
        """监控任务直到完成或失败"""
        return self.job_manager.monitor_job(job_arn, check_interval)
    
    def get_results_preview_only(self, job_arn: str, output_bucket: str, output_prefix: str, max_preview_lines: int = 3) -> Dict:
        """
        获取任务结果预览和文件位置
        
        Args:
            job_arn: 任务ARN
            output_bucket: 输出bucket
            output_prefix: 输出前缀
            max_preview_lines: 最大预览行数（文本/图片默认3行，视频建议1行）
        """
        return self.job_manager.get_results_preview(job_arn, output_bucket, output_prefix, max_preview_lines)
    
    # 保留向后兼容的方法名
    def get_job_results(self, job_arn: str, output_bucket: str, output_prefix: str) -> List[Dict]:
        """获取任务结果（向后兼容）"""
        result = self.get_results_preview_only(job_arn, output_bucket, output_prefix)
        return result['preview']
    
    def create_video_batch_job(
        self,
        input_bucket: str,
        input_prefix: str,
        output_bucket: str,
        output_prefix: str,
        model_id: str,
        role_arn: str,
        system_prompt: str,
        user_prompt: str,
        job_name: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """创建视频批量推理任务"""
        try:
            # 规范化前缀
            input_prefix = S3Manager.normalize_prefix(input_prefix)
            output_prefix = S3Manager.normalize_prefix(output_prefix)
            
            # 准备视频批量数据（流式处理，返回处理数量和文件名）
            video_count, filename = self.video_processor.prepare_batch_data(
                input_bucket, input_prefix, system_prompt,
                user_prompt, model_id, progress_callback
            )
            
            # 上传JSONL文件到S3
            s3_key = f"{input_prefix}{filename}" if input_prefix else filename
            input_s3_uri = self.upload_to_s3(filename, input_bucket, s3_key)
            
            if progress_callback:
                progress_callback('upload', 1, 1, f'✅ JSONL文件已上传到: {input_s3_uri}')
            
            # 清理本地临时文件
            if os.path.exists(filename):
                os.remove(filename)
            
            # 创建批处理任务
            result = self.create_batch_job_from_jsonl(
                input_s3_uri, output_bucket, output_prefix,
                model_id, role_arn, job_name
            )
            
            if result['success']:
                result['message'] = f"成功提交视频批量推理任务，共{video_count}个视频"
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f"创建视频批量任务失败: {str(e)}"
            }
    
    # 权限验证方法
    def validate_permissions(self, role_arn: str, input_bucket: str, output_bucket: str, model_id: str = None) -> Dict:
        """验证权限配置"""
        return self.validator.validate_permissions(role_arn, input_bucket, output_bucket, model_id)
    
    # 单次推理验证方法
    def validate_single_text_inference(
        self,
        use_jsonl: bool,
        input_bucket: str,
        input_prefix: str,
        jsonl_s3_uri: str,
        prompt: str,
        model_id: str
    ) -> Dict:
        """验证文本批处理的单次推理"""
        return self.inference_validator.validate_text_inference(
            use_jsonl, input_bucket, input_prefix, jsonl_s3_uri, prompt, model_id
        )
    
    def validate_single_image_inference(
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
        return self.inference_validator.validate_image_inference(
            use_jsonl, input_bucket, input_prefix, jsonl_s3_uri,
            system_prompt, user_prompt, model_id
        )
    
    def validate_single_video_inference(
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
        return self.inference_validator.validate_video_inference(
            use_jsonl, input_bucket, input_prefix, jsonl_s3_uri,
            system_prompt, user_prompt, model_id
        )
