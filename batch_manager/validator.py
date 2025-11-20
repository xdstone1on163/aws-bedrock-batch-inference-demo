"""
权限验证模块
验证Role ARN对S3和Bedrock的基础配置
注意：实际权限将在任务提交时由AWS服务验证
"""
import boto3
import logging
from typing import Dict

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - [PermissionValidator] - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class PermissionValidator:
    """处理AWS基础配置验证"""
    
    def __init__(self, region: str, s3_manager=None):
        """
        初始化权限验证器
        
        Args:
            region: AWS区域
            s3_manager: S3管理器实例（可选，用于向后兼容）
        """
        self.region = region
        self.sts = boto3.client('sts', region_name=region)
        logger.info(f"权限验证器初始化完成，区域: {region}")
    
    def validate_permissions(
        self,
        role_arn: str,
        input_bucket: str,
        output_bucket: str,
        model_id: str = None
    ) -> Dict:
        """
        验证基础配置（格式检查）
        注意：实际的S3和Bedrock权限将在任务提交时由AWS服务验证
        
        Args:
            role_arn: IAM角色ARN
            input_bucket: 输入bucket
            output_bucket: 输出bucket
            model_id: Bedrock模型ID（可选）
            
        Returns:
            验证结果字典
        """
        logger.info(f"🔍 开始基础配置验证 - Role: {role_arn}")
        logger.debug(f"参数 - Input Bucket: {input_bucket}, Output Bucket: {output_bucket}")
        if model_id:
            logger.debug(f"参数 - Model ID: {model_id}")
        
        results = {
            'valid': True,
            'checks': [],
            'errors': [],
            'warnings': []
        }
        
        try:
            # 1. 检查Role ARN格式
            logger.debug("步骤1: 检查Role ARN格式...")
            if not role_arn or not role_arn.startswith('arn:aws:iam::'):
                results['valid'] = False
                results['errors'].append(f"✗ Role ARN格式不正确: {role_arn}")
                logger.error(f"Role ARN格式错误: {role_arn}")
                return results
            
            results['checks'].append(f"✓ Role ARN格式正确")
            logger.debug(f"✅ Role ARN格式验证通过")
            
            # 2. 检查当前身份（仅用于记录）
            logger.debug("步骤2: 获取当前身份信息...")
            try:
                identity = self.sts.get_caller_identity()
                current_arn = identity['Arn']
                results['checks'].append(f"✓ 当前身份: {current_arn}")
                logger.info(f"当前身份: {current_arn}")
            except Exception as e:
                logger.warning(f"无法获取当前身份: {str(e)}")
                results['warnings'].append(f"⚠ 无法获取当前身份信息")
            
            # 3. 检查输入bucket名称格式
            logger.debug("步骤3: 检查输入bucket名称格式...")
            if self._is_valid_bucket_name(input_bucket):
                results['checks'].append(f"✓ 输入bucket名称格式有效: {input_bucket}")
                logger.debug(f"✅ 输入bucket名称格式有效")
            else:
                results['valid'] = False
                results['errors'].append(f"✗ 输入bucket名称格式无效: {input_bucket}")
                logger.error(f"❌ 输入bucket名称格式无效")
            
            # 4. 检查输出bucket名称格式
            logger.debug("步骤4: 检查输出bucket名称格式...")
            if self._is_valid_bucket_name(output_bucket):
                results['checks'].append(f"✓ 输出bucket名称格式有效: {output_bucket}")
                logger.debug(f"✅ 输出bucket名称格式有效")
            else:
                results['valid'] = False
                results['errors'].append(f"✗ 输出bucket名称格式无效: {output_bucket}")
                logger.error(f"❌ 输出bucket名称格式无效")
            
            # 5. 检查模型ID格式（如果提供）
            if model_id:
                logger.debug("步骤5: 检查模型ID格式...")
                if self._is_valid_model_id(model_id):
                    results['checks'].append(f"✓ 模型ID格式有效: {model_id}")
                    logger.debug(f"✅ 模型ID格式有效")
                else:
                    results['valid'] = False
                    results['errors'].append(f"✗ 模型ID格式无效: {model_id}")
                    logger.error(f"❌ 模型ID格式无效")
            
            # 添加重要提示
            results['warnings'].append("⚠ 实际的S3和Bedrock权限将在任务提交时由AWS服务验证")
            results['warnings'].append("⚠ 如果权限不足，任务会在执行时失败并提供详细错误信息")
            results['warnings'].append("⚠ 建议先用少量文件测试权限配置")
            
            logger.info(f"基础配置验证完成 - 结果: {'通过' if results['valid'] else '失败'}")
            
        except Exception as e:
            results['valid'] = False
            results['errors'].append(f"验证过程出错: {str(e)}")
            logger.error(f"❌ 验证过程出错: {str(e)}", exc_info=True)
        
        return results
    
    def _is_valid_bucket_name(self, bucket_name: str) -> bool:
        """
        检查S3 bucket名称格式是否有效
        
        Args:
            bucket_name: bucket名称
            
        Returns:
            是否有效
        """
        if not bucket_name:
            return False
        
        # S3 bucket命名规则基础检查
        # - 长度在3-63之间
        # - 只包含小写字母、数字、点和连字符
        # - 以字母或数字开头和结尾
        import re
        if len(bucket_name) < 3 or len(bucket_name) > 63:
            return False
        
        pattern = r'^[a-z0-9][a-z0-9\.\-]*[a-z0-9]$'
        return bool(re.match(pattern, bucket_name))
    
    def _is_valid_model_id(self, model_id: str) -> bool:
        """
        检查模型ID格式是否有效
        
        Args:
            model_id: 模型ID
            
        Returns:
            是否有效
        """
        if not model_id:
            return False
        
        # 模型ID基础格式检查
        # 通常格式如: anthropic.claude-3-haiku-20240307-v1:0
        # 或: us.anthropic.claude-3-haiku-20240307-v1:0
        # 或: amazon.titan-text-express-v1
        return len(model_id) > 0 and not model_id.isspace()
