"""
状态管理模块
处理任务状态的保存、加载和恢复
"""
import json
import os
from datetime import datetime
from config import STATE_FILE, current_job_info
from batch_manager import BatchInferenceManager


def save_job_state(job_arn: str, job_info: dict):
    """保存任务状态到文件"""
    try:
        # 读取现有状态
        states = {}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                states = json.load(f)
        
        # 更新状态（不保存manager对象）
        states[job_arn] = {
            'job_arn': job_arn,
            'output_bucket': job_info.get('output_bucket'),
            'output_prefix': job_info.get('output_prefix'),
            'aws_region': job_info.get('aws_region'),
            'input_bucket': job_info.get('input_bucket'),
            'input_prefix': job_info.get('input_prefix'),
            'timestamp': datetime.now().isoformat()
        }
        
        # 保存到文件
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(states, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"保存状态失败: {e}")


def load_job_state(job_arn: str = None) -> dict:
    """加载任务状态"""
    try:
        if not os.path.exists(STATE_FILE):
            return None
            
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            states = json.load(f)
        
        if job_arn:
            return states.get(job_arn)
        else:
            # 返回最新的任务
            if states:
                latest = max(states.values(), key=lambda x: x.get('timestamp', ''))
                return latest
            return None
            
    except Exception as e:
        print(f"加载状态失败: {e}")
        return None


def get_all_job_states() -> list:
    """获取所有任务状态列表"""
    try:
        if not os.path.exists(STATE_FILE):
            return []
            
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            states = json.load(f)
        
        # 按时间倒序排序
        job_list = sorted(states.values(), key=lambda x: x.get('timestamp', ''), reverse=True)
        return job_list[:10]  # 只返回最近10个任务
        
    except Exception as e:
        print(f"获取任务列表失败: {e}")
        return []


def create_batch_manager(bedrock_region: str = 'us-east-1', s3_region: str = 'us-east-1') -> BatchInferenceManager:
    """创建批处理管理器"""
    return BatchInferenceManager(bedrock_region=bedrock_region, s3_region=s3_region)
