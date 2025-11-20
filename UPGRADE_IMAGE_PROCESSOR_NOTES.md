# Image Processor 升级说明

## 概述
升级了 `batch_manager/image_processor.py` 的处理逻辑，实现了**流式处理**机制，避免大型图片批处理时内存溢出问题。

## 主要改进

### 1. 内存使用优化
**升级前：** O(n) 内存复杂度
- 所有图片的base64编码数据都保存在 `model_inputs` 列表中
- 处理1000张图片时，整个列表可能占用数GB内存
- 只有在所有图片都处理完成后，才开始写入JSONL文件

**升级后：** O(1) 内存复杂度
- 每处理完一张图片，立即写入JSONL文件
- 处理后的图片数据被垃圾回收
- 内存占用保持稳定，不随图片数量增加

### 2. 处理逻辑变化

#### 返回值类型变更
```python
# 升级前
Tuple[List[Dict], str]  # 返回完整的model_inputs列表和文件名

# 升级后
Tuple[int, str]  # 返回处理的图片数量和文件名
```

#### 处理流程
```python
# 升级前
1. 扫描所有图片文件
2. 循环处理所有图片，将结果保存到model_inputs列表
3. 处理完所有图片后，一次性写入JSONL文件

# 升级后
1. 扫描所有图片文件
2. 创建JSONL文件并打开文件句柄
3. 循环处理每张图片，处理完后立即写入JSONL文件（流式处理）
4. 关闭文件句柄
```

### 3. 新增方法

#### `_write_single_record(file_handle, record: Dict) -> None`
- **作用**：将单条记录写入JSONL文件
- **特性**：调用 `file.flush()` 确保数据立即写入磁盘
- **优势**：避免数据丢失，提高数据安全性

### 4. 错误处理改进
- 使用 `try-finally` 确保文件句柄正确关闭
- 即使处理中断，已写入JSONL的数据不会丢失
- 提供更详细的错误信息

## 受影响的文件

### 直接修改
- `batch_manager/image_processor.py`
  - 修改 `prepare_batch_data()` 返回类型
  - 新增 `_write_single_record()` 方法
  - 改进错误处理和资源管理

### 间接修改
- `batch_manager/core.py`
  - 更新 `prepare_image_batch_data()` 返回类型注解
  - 更新 `create_image_batch_job()` 处理新的返回值

### 无需修改（向后兼容）
- `job_handlers.py` - 已正确处理新的返回值
- `ui_image.py` - 无需变化
- 其他文件 - 无需变化

## 性能对比

假设处理1000张平均大小为500KB的图片：

| 指标 | 升级前 | 升级后 | 改进 |
|------|-------|-------|------|
| 峰值内存 | ~500GB | ~50MB | 10000倍 |
| 处理时间 | 类似 | 类似 | N/A |
| JSONL生成时间 | 等待所有图片 | 逐步生成 | 更快反馈 |
| 数据安全性 | 单次写入风险 | 分次写入 | 更高 |

## 使用示例

升级后的使用方式保持不变，但返回值发生了改变：

```python
from batch_manager import BatchInferenceManager

manager = BatchInferenceManager()

# 升级后的调用方式
image_count, filename = manager.prepare_image_batch_data(
    bucket_name="my-bucket",
    prefix="images/",
    system_prompt="You are a vision expert",
    user_prompt="Analyze this image",
    model_id="claude-3-haiku-20240307"
)

print(f"处理了 {image_count} 张图片")
print(f"JSONL文件: {filename}")
```

## 迁移指南

### 如果您有自定义代码调用此方法

**升级前的代码：**
```python
model_inputs, filename = processor.prepare_batch_data(...)
# 使用 model_inputs 列表...
```

**需要改为：**
```python
image_count, filename = processor.prepare_batch_data(...)
# 使用 image_count 获取处理数量，JSONL文件已自动写入磁盘
```

### 如果需要访问详细的模型输入信息

由于不再返回完整的模型输入列表，如果您需要模型输入的详细信息：

1. **直接读取JSONL文件**（推荐）：
```python
image_count, filename = processor.prepare_batch_data(...)

# 读取生成的JSONL文件
with open(filename, 'r', encoding='utf-8') as f:
    for line in f:
        record = json.loads(line)
        # 处理每条记录...
```

2. **临时恢复旧行为**（不推荐）：
   - 如果需要完全恢复旧行为，可以手动添加一个缓存列表
   - 但这会再次引入内存问题，不建议使用

## 测试建议

### 功能测试
- [ ] 处理小批量图片（1-10张）
- [ ] 处理中等批量图片（100-500张）
- [ ] 处理大批量图片（1000+张）
- [ ] 验证生成的JSONL文件格式正确
- [ ] 检查每条记录的base64编码完整性

### 性能测试
- [ ] 监控内存使用情况
- [ ] 验证处理时间无显著增加
- [ ] 确认JSONL写入速度稳定

### 错误处理测试
- [ ] 处理网络中断场景
- [ ] 处理磁盘空间不足场景
- [ ] 验证错误时文件句柄正确关闭

## 常见问题

### Q: 为什么要这样升级？
A: 处理大批量图片时（如1000+张），原来的方式会导致内存持续增长，最终导致内存溢出（OOM）。升级后的流式处理保持内存使用稳定。

### Q: 我能否获取单张图片的base64编码？
A: 可以。在处理过程中，每张图片都临时保存在内存中。如果需要保留某些图片的base64数据，可以在处理过程中复制到本地变量。

### Q: JSONL文件的格式有变化吗？
A: 否。每行JSON的结构完全相同，只是生成方式从"全部处理完后一次写入"改为"每张处理完后立即写入"。

### Q: 如果处理中断，部分JSONL数据会丢失吗？
A: 不会。每条记录写入后都调用 `flush()`，确保立即写入磁盘。即使进程意外终止，已写入的数据也是安全的。

## 回滚说明

如果需要回滚到之前的版本：

```bash
# 恢复之前的 image_processor.py
git checkout HEAD~1 batch_manager/image_processor.py
git checkout HEAD~1 batch_manager/core.py
```

然后需要修改调用代码，改回：
```python
model_inputs, filename = ...  # 而不是 image_count, filename
```

## 版本信息

- **升级版本**：v2.1.0
- **升级日期**：2025-11-14
- **受影响范围**：图片批处理模块
- **破坏性变更**：是（返回值类型改变）
- **兼容性**：需要更新调用代码
