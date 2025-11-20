"""
配置文件
包含模型配置、常量等
"""

# 支持的模型列表 - 文本模式（所有支持批处理的模型 - 使用Cross-region Inference Profiles）
TEXT_MODELS = {
    # === Claude 3 系列 ===
    "Claude 3 Haiku": "us.anthropic.claude-3-haiku-20240307-v1:0",
    "Claude 3 Sonnet": "us.anthropic.claude-3-sonnet-20240229-v1:0",
    "Claude 3 Opus": "us.anthropic.claude-3-opus-20240229-v1:0",
    
    # === Claude 3.5 系列 ===
    "Claude 3.5 Haiku": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    "Claude 3.5 Sonnet": "us.anthropic.claude-3-5-sonnet-20240620-v1:0",
    "Claude 3.5 Sonnet v2": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    
    # === Claude 3.7 系列 ===
    "Claude 3.7 Sonnet": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    
    # === Claude 4.x 系列 ===
    "Claude Haiku 4.5": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "Claude Sonnet 4": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "Claude Sonnet 4.5": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    
    # === Amazon Nova 系列 ===
    "Nova Micro": "us.amazon.nova-micro-v1:0",
    "Nova Lite": "us.amazon.nova-lite-v1:0",
    "Nova Pro": "us.amazon.nova-pro-v1:0",
    "Nova Premier": "us.amazon.nova-premier-v1:0",
}

# 支持的模型列表 - 图片模式（支持Vision/Multimodal的模型 - 使用Cross-region Inference Profiles）
IMAGE_MODELS = {
    # === Claude 3 系列 (Vision) ===
    "Claude 3 Haiku": "us.anthropic.claude-3-haiku-20240307-v1:0",
    "Claude 3 Sonnet": "us.anthropic.claude-3-sonnet-20240229-v1:0",
    "Claude 3 Opus": "us.anthropic.claude-3-opus-20240229-v1:0",
    
    # === Claude 3.5 系列 (Vision) ===
    "Claude 3.5 Haiku": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    "Claude 3.5 Sonnet": "us.anthropic.claude-3-5-sonnet-20240620-v1:0",
    "Claude 3.5 Sonnet v2": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    
    # === Claude 3.7 系列 (Vision) ===
    "Claude 3.7 Sonnet": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    
    # === Claude 4.x 系列 (Vision) ===
    "Claude Haiku 4.5": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "Claude Sonnet 4": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "Claude Sonnet 4.5": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    
    # === Amazon Nova 多模态系列（文本+图片） ===
    "Nova Lite (Image)": "us.amazon.nova-lite-v1:0",
    "Nova Pro (Image)": "us.amazon.nova-pro-v1:0",
    "Nova Premier (Image)": "us.amazon.nova-premier-v1:0",
}

# 支持的模型列表 - 视频模式（仅Nova Pro和Premier支持视频 - 使用Cross-region Inference Profiles）
VIDEO_MODELS = {
    # === Amazon Nova 视频系列（文本+图片+视频） ===
    "Nova Pro (Video)": "us.amazon.nova-pro-v1:0",
    "Nova Premier (Video)": "us.amazon.nova-premier-v1:0",
}

# 状态文件路径
STATE_FILE = 'job_states.json'

# 全局变量存储当前任务
current_job_info = {
    'job_arn': None,
    'manager': None,
    'output_bucket': None,
    'output_prefix': None,
    'aws_region': None,
    'input_bucket': None,
    'input_prefix': None
}

# AWS主题配置
AWS_THEME_CONFIG = {
    'body_background_fill': "#FFFFFF",
    'body_text_color': "#232F3E",
    'button_primary_background_fill': "#FF9900",
    'button_primary_background_fill_hover': "#EC7211",
    'button_primary_text_color': "#FFFFFF",
    'button_secondary_background_fill': "#232F3E",
    'button_secondary_background_fill_hover': "#37475A",
    'button_secondary_text_color': "#FFFFFF",
    'block_title_text_color': "#232F3E",
    'block_label_text_color': "#232F3E",
    'input_background_fill': "#FFFFFF",
    'input_border_color': "#AAB7B8"
}

# CSS样式
AWS_CSS = """
.gradio-container {
    font-family: "Amazon Ember", "Helvetica Neue", Roboto, Arial, sans-serif !important;
}
h1 {
    color: #232F3E !important;
    border-bottom: 3px solid #FF9900 !important;
    padding-bottom: 10px !important;
}
h2, h3 {
    color: #232F3E !important;
}
.orange-accent {
    color: #FF9900 !important;
}
"""
