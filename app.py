"""
AWS Bedrock 批量推理 Gradio Demo
主入口文件 - 重构版
"""
import gradio as gr
from config import AWS_THEME_CONFIG, AWS_CSS
from ui_text import create_text_batch_interface
from ui_image import create_image_batch_interface
from ui_video import create_video_batch_interface


def create_interface():
    """创建Gradio界面"""
    
    # AWS配色主题
    aws_theme = gr.themes.Soft(
        primary_hue="orange",
        secondary_hue="blue",
        neutral_hue="slate",
    ).set(**AWS_THEME_CONFIG)
    
    with gr.Blocks(
        title="AWS Bedrock 批量推理 Demo",
        theme=aws_theme,
        css=AWS_CSS
    ) as demo:
        
        # 标题
        gr.Markdown(
            """
            # 🚀 AWS Bedrock 批量推理 Demo
            ### <span style="color: #FF9900;">文本、图片与视频批处理平台</span>
            
            支持文本、图片和视频三种批量推理模式
            """,
            elem_classes=["header"]
        )
        
        # 状态存储
        job_arn_state = gr.State(None)
        results_ready_state = gr.State(None)
        
        # 创建三模式Tab界面
        with gr.Tabs() as tabs:
            # 文本批处理Tab
            with gr.Tab("📝 文本批处理", id="text_tab"):
                create_text_batch_interface(job_arn_state, results_ready_state)
            
            # 图片批处理Tab
            with gr.Tab("🖼️ 图片批处理", id="image_tab"):
                create_image_batch_interface(job_arn_state, results_ready_state)
            
            # 视频批处理Tab
            with gr.Tab("🎬 视频批处理", id="video_tab"):
                create_video_batch_interface(job_arn_state, results_ready_state)
    
    return demo


if __name__ == "__main__":
    demo = create_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
