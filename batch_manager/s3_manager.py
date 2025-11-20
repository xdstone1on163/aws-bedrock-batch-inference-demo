"""
S3操作管理模块
"""
import boto3
import os
import logging
from typing import List, Dict

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - [S3Manager] - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class S3Manager:
    """处理所有S3相关操作"""
    
    def __init__(self, region: str = 'us-east-1'):
        """
        初始化S3管理器
        
        Args:
            region: S3所在区域
        """
        self.s3 = boto3.client('s3', region_name=region)
        self.region = region
        logger.info(f"S3Manager初始化完成，区域: {region}")
    
    def list_files(self, bucket_name: str, prefix: str) -> List[Dict]:
        """
        列出bucket中的文件（支持分页）
        
        Args:
            bucket_name: S3 bucket名称
            prefix: 文件路径前缀
            
        Returns:
            文件列表
        """
        try:
            logger.debug(f"开始列出S3文件 - Bucket: {bucket_name}, Prefix: {prefix}")
            files = []
            continuation_token = None
            page_count = 0
            total_objects = 0
            skipped_objects = 0
            
            while True:
                page_count += 1
                # 构建请求参数
                params = {'Bucket': bucket_name, 'Prefix': prefix}
                if continuation_token:
                    params['ContinuationToken'] = continuation_token
                    logger.debug(f"获取第{page_count}页数据，使用ContinuationToken")
                else:
                    logger.debug(f"获取第{page_count}页数据")
                
                response = self.s3.list_objects_v2(**params)
                
                if 'Contents' not in response:
                    logger.warning(f"第{page_count}页没有找到任何内容")
                    break
                
                page_objects = len(response['Contents'])
                total_objects += page_objects
                logger.debug(f"第{page_count}页返回 {page_objects} 个对象")
                
                for obj in response['Contents']:
                    # 跳过目录本身和以/结尾的对象
                    if obj['Key'] == prefix or obj['Key'].endswith('/'):
                        skipped_objects += 1
                        logger.debug(f"跳过目录对象: {obj['Key']}")
                        continue
                    
                    # 跳过大小为0的文件（可能是目录标记）
                    if obj['Size'] == 0:
                        skipped_objects += 1
                        logger.debug(f"跳过空文件: {obj['Key']}")
                        continue
                    
                    files.append({
                        'file_path': obj['Key'],
                        'file_name': os.path.basename(obj['Key']),
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S')
                    })
                
                # 检查是否还有更多数据需要分页获取
                if response.get('IsTruncated', False):
                    continuation_token = response.get('NextContinuationToken')
                    logger.debug(f"响应被截断，需要继续分页")
                else:
                    logger.debug(f"没有更多数据，分页结束")
                    break
            
            logger.info(f"✅ S3文件列表完成 - 共扫描 {total_objects} 个对象，跳过 {skipped_objects} 个，返回 {len(files)} 个有效文件")
            return files
            
        except Exception as e:
            logger.error(f"❌ 列出S3文件失败: {str(e)}", exc_info=True)
            raise Exception(f"列出文件失败: {str(e)}")
    
    def read_file(self, bucket_name: str, file_path: str) -> str:
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
    
    def read_binary_file(self, bucket_name: str, file_path: str) -> bytes:
        """
        读取S3二进制文件（如图片）
        
        Args:
            bucket_name: S3 bucket名称
            file_path: 文件路径
            
        Returns:
            文件二进制数据
        """
        try:
            response = self.s3.get_object(Bucket=bucket_name, Key=file_path)
            return response['Body'].read()
        except Exception as e:
            raise Exception(f"读取二进制文件失败 {file_path}: {str(e)}")
    
    def upload_file(self, local_file: str, bucket_name: str, s3_key: str) -> str:
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
            return f"s3://{bucket_name}/{s3_key}"
        except Exception as e:
            raise Exception(f"上传文件到S3失败: {str(e)}")
    
    def upload_files(self, local_files: List[str], bucket_name: str, prefix: str = "") -> List[str]:
        """
        批量上传本地文件到S3
        
        Args:
            local_files: 本地文件路径列表
            bucket_name: S3 bucket名称
            prefix: S3路径前缀
            
        Returns:
            上传后的S3文件路径列表
        """
        try:
            uploaded_files = []
            
            for local_file in local_files:
                if not os.path.exists(local_file):
                    raise Exception(f"本地文件不存在: {local_file}")
                
                filename = os.path.basename(local_file)
                s3_key = f"{prefix}{filename}" if prefix else filename
                
                self.s3.upload_file(local_file, bucket_name, s3_key)
                uploaded_files.append(s3_key)
            
            return uploaded_files
            
        except Exception as e:
            raise Exception(f"批量上传文件失败: {str(e)}")
    
    @staticmethod
    def normalize_prefix(prefix: str) -> str:
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
    
    def check_bucket_access(self, bucket_name: str) -> bool:
        """
        检查bucket访问权限
        
        Args:
            bucket_name: S3 bucket名称
            
        Returns:
            是否可访问
        """
        try:
            self.s3.head_bucket(Bucket=bucket_name)
            return True
        except Exception:
            return False
