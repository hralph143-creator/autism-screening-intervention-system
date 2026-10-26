# 基于深度学习的自闭症筛查与干预系统

这是一个在 Windows 本机运行的儿童档案、视频客观特征分析、日常行为观察、家庭互动活动记录、综合历史与报告整理系统。当前已完成第一至第六阶段，业务数据可按儿童统一查询，并可生成适合 A4 打印或通过浏览器保存为 PDF 的综合报告。

> 系统只提供姿态/面部检测覆盖率、头部位置变化、上肢运动变化和数据质量摘要，不输出自闭症诊断、风险概率或医疗建议，也不能替代专业评估。

## 已完成功能

- Vue 3、TypeScript、Vite、Element Plus、ECharts 前端
- FastAPI、SQLAlchemy、SQLite 后端与 HttpOnly Cookie 登录
- 匿名化儿童档案 CRUD、搜索、分页与首页真实统计
- MP4 上传与儿童档案关联，提交前强制确认监护人授权
- 后端真实校验扩展名、MP4 文件头、大小、时长、分辨率、帧率、首尾可解码性
- MediaPipe Tasks `VIDEO` 模式，CPU 单工作线程，长视频约 2 帧/秒采样，短视频自适应保证约 8 个采样位置
- Pose 与 Face 模型均使用官方 `.task` 文件并执行真实加载检查
- `PENDING / RUNNING / COMPLETED / FAILED / INTERRUPTED` 完整任务状态
- 服务重启时把遗留 `RUNNING` 任务标为可重试的 `INTERRUPTED`
- 姿态与面部覆盖率、尺度归一化运动量、缺失段和多人歧义处理
- 3–5 张可用检测结果帧、ECharts 趋势图、任务筛选、失败重试与安全删除
- 受登录保护的列表、结果和结果帧接口；视频使用 UUID 文件名保存
- `0002_create_children` 与 `0003_create_video_analyses` 增量迁移，不清空旧数据
- 自动化测试、真实模型加载验证和实际视频验证脚本
- 非标准化行为观察表，包含 6 个维度、12 个中性观察项目和 5 种明确区分的记录状态
- 观察记录创建、查询、编辑、删除、日期筛选、儿童历史查询及可选视频关联
- 基于实际填写内容生成确定性辅助摘要和数据完整性指标，不调用外部大模型
- `0004_create_observation_records` 增量迁移，保留前三阶段全部数据
- 12 项内置家庭互动活动，覆盖社交互动、语言与沟通、注意力与共同活动、日常生活技能 4 类
- 活动资源搜索、分类与儿童月龄参考筛选，活动详情包含目标、材料、步骤、建议时长及注意事项
- 儿童活动记录创建、查询、编辑、删除、日期筛选、分类统计与档案历史入口
- 管理员可新增和编辑活动资源，并通过启用/停用保留既有活动记录及不可变内容快照
- `0005_create_activities_and_records` 增量迁移，幂等补齐内置活动且不覆盖管理员修改
- 按儿童统一汇总视频、观察和活动记录的综合概览、月度计数图和分页时间线
- 综合时间线支持记录类型、日期范围、正序/倒序筛选，并可跳转至原业务详情
- 基于实时数据库生成“儿童行为观察与活动记录综合报告”，支持日期范围和记录类型选择
- A4 报告预览、浏览器打印及“保存为 PDF”，缺失数据和失败任务均真实标注
- 报告最多纳入按业务日期倒序排列的 200 条记录，超过时明确提示，不创建报告快照表
- 所有历史与报告接口均受管理员会话保护，不返回视频路径或完整关键点序列

## 环境

- Windows 10/11 64 位
- Python 3.11 或 3.12
- Node.js 20 或更高版本
- npm 10 或更高版本
- 纯 CPU 可运行，不依赖 CUDA、PyTorch、TensorFlow、Redis 或外部任务队列

已核验的视频依赖版本：MediaPipe `0.10.32`、OpenCV contrib `4.12.0.88`、NumPy `2.2.6`。模型来自 Google MediaPipe 官方存储地址。

## 首次安装

在项目根目录双击 `setup.bat`。脚本会：

1. 检查 Python、Node.js 与 npm；
2. 创建 `.venv` 并安装前后端依赖；
3. 下载官方 Pose Lite 与 Face Landmarker 模型，记录 SHA-256，并真实创建模型实例；
4. 初始化 SQLite 并依次执行增量迁移；
5. 检查依赖、数据库、模型和前端类型。

模型也可独立下载或修复：

```powershell
.venv\Scripts\python.exe scripts\download_models.py
```

模型缺失时，档案等既有页面仍可使用；视频页面会明确显示不可用原因，上传接口返回 `503`，不会伪装为分析成功。

## 启动与检查

双击 `run.bat` 启动前后端。脚本会检查环境、模型和端口，确认两个服务可访问后才打开浏览器；如果系统已经正常运行，会直接复用现有服务，不会重复启动或误报端口占用。

- 前端：<http://127.0.0.1:5173>
- 后端：<http://127.0.0.1:8001>
- API 文档：<http://127.0.0.1:8001/docs>

双击 `check.bat` 可检查运行环境、数据库表、模型真实加载状态及已启动的服务。

## 视频处理边界

- 仅支持 `.mp4`，最大 100 MB，最长 120 秒。
- 文件与结果保存在本机，不由本项目上传到云端。
- 同一儿童、同一文件内容已有等待中/运行中/已完成任务时会拒绝重复提交。
- 每个分析任务创建独立模型实例，避免跨线程共享跟踪状态。
- MediaPipe 视频时间戳严格递增；关键点缺失、多人/多面孔帧不拼接成单人轨迹。
- 运动量使用肩部—髋部躯干尺度归一化；不可信的大幅跳变保留为缺失，趋势图不跨缺失段连线。
- 无人、面部不可见或有效帧太少时，任务仍可完成，但明确显示“有效数据不足”。
- 上传成功只表示文件保存并入队，只有 `COMPLETED` 才表示分析成功。

## 数据目录

```text
data/
  app.db                  SQLite 数据库
  uploads/                UUID 命名的原视频
  analysis_results/<id>/  带关键点的结果帧
models/
  pose_landmarker_lite.task
  face_landmarker.task
```

以上运行数据与模型文件均被 Git 忽略。删除一个已结束的分析任务时，会同时删除其原视频、结果帧和数据库记录。等待或运行中的任务不能删除。

## 主要接口

除健康检查和认证接口外，以下接口均需登录：

| 方法 | 地址 | 说明 |
|---|---|---|
| GET | `/api/models/status` | 检查模型文件并真实加载 |
| GET | `/api/video-analyses` | 分页并按儿童/状态筛选任务 |
| POST | `/api/video-analyses` | 授权确认、上传校验并入队 |
| GET | `/api/video-analyses/{id}` | 查询状态与进度 |
| GET | `/api/video-analyses/{id}/status` | 查询状态与进度（显式别名） |
| GET | `/api/video-analyses/{id}/result` | 获取已完成的客观结果 |
| GET | `/api/video-analyses/{id}/frames/{filename}` | 受保护地读取结果帧 |
| POST | `/api/video-analyses/{id}/retry` | 重试失败或中断任务 |
| DELETE | `/api/video-analyses/{id}` | 删除已结束任务和文件 |
| GET | `/api/observations/form-definition` | 获取统一的观察维度、项目与选项定义 |
| GET | `/api/observations` | 按儿童、日期分页查询观察记录 |
| POST | `/api/observations` | 创建行为观察记录 |
| GET | `/api/observations/{id}` | 查看记录、动态摘要和关联视频 |
| PUT | `/api/observations/{id}` | 更新观察记录 |
| DELETE | `/api/observations/{id}` | 删除观察记录 |
| GET | `/api/children/{id}/observations` | 查询指定儿童的观察历史 |
| GET | `/api/activities` | 搜索、分类或按儿童月龄参考筛选活动资源 |
| POST | `/api/activities` | 新增自定义活动资源 |
| GET | `/api/activities/{id}` | 查看活动详情 |
| PUT | `/api/activities/{id}` | 编辑活动资源 |
| PATCH | `/api/activities/{id}/status` | 启用或停用活动资源 |
| GET | `/api/activity-records` | 分页筛选儿童活动记录 |
| POST | `/api/activity-records` | 创建儿童活动记录并保存活动快照 |
| GET | `/api/activity-records/stats` | 获取真实记录数量、完成情况与分类统计 |
| GET | `/api/activity-records/{id}` | 查看活动记录详情 |
| PUT | `/api/activity-records/{id}` | 编辑活动记录 |
| DELETE | `/api/activity-records/{id}` | 删除活动记录 |
| GET | `/api/children/{id}/activity-records` | 查询指定儿童的活动历史 |
| GET | `/api/children/{id}/overview` | 获取指定儿童的档案信息、真实记录计数和轻量统计 |
| GET | `/api/children/{id}/timeline` | 按类型、日期、顺序分页查询统一历史时间线 |
| GET | `/api/children/{id}/report` | 按日期和记录类型实时生成综合报告数据 |

儿童档案接口仍位于 `/api/children`，首页统计位于 `/api/dashboard/stats`。

## 开发与验证

```powershell
# 后端测试（含上传校验、缺失模型、重复提交、队列成功/失败/中断、鉴权）
.venv\Scripts\python.exe -m pytest backend\tests -q

# 前端检查与生产构建
npm --prefix frontend run typecheck
npm --prefix frontend run build

# 模型真实加载
.venv\Scripts\python.exe scripts\check_models.py

# 使用官方或已授权的人像帧验证 VIDEO 模式面部关键点
.venv\Scripts\python.exe scripts\verify_face_model.py "D:\path\authorized-portrait.jpg"

# 使用自备且已授权的实际 MP4 验证真实推理，不写业务数据库
.venv\Scripts\python.exe scripts\verify_actual_analysis.py "D:\path\authorized-video.mp4"

# 在临时数据库中验证从管理员初始化到综合报告的完整流程
.venv\Scripts\python.exe scripts\verify_stage6_flow.py "D:\path\authorized-video.mp4"
```

自动化测试中的队列推理会使用可控替身来稳定覆盖状态机；`check_models.py` 与 `verify_actual_analysis.py` 则明确执行真实 MediaPipe 模型，二者不会混为一谈。

## 配置

配置集中在 `backend/app/core/config.py`：

- `APP_ENV`、`APP_HOST`、`APP_PORT`、`LOG_LEVEL`
- `APP_DATA_DIR`：数据库、上传和结果目录的根目录
- `APP_MODEL_DIR`：模型目录
- `FRONTEND_ORIGINS`：允许的前端来源
- `MAX_VIDEO_BYTES`：默认 100 MB
- `MAX_VIDEO_SECONDS`：默认 120 秒
- `ANALYSIS_SAMPLE_FPS`：默认 2 帧/秒

## 隐私与限制

- 请只处理已获得明确授权的视频，避免录入真实姓名等不必要信息。
- 本机保存不等于绝对安全；应保护 Windows 账户、磁盘和项目目录权限。
- 当前队列是进程内单工作线程，适合毕业设计和单机轻量使用，不适合多机并发生产环境。
- Pose/Face 的有效率会受遮挡、距离、光照、镜头角度和多人画面影响。
- 本阶段没有模型训练、疾病分类或临床有效性验证。
- 行为观察表不是 M-CHAT-R/F、ADOS 或其他临床标准化量表；摘要只复述实际记录和缺失情况，不解释为病情改善或恶化。
- 观察备注最长 4000 字，不应填写不必要的真实姓名、联系方式或其他身份信息。
- 家庭互动活动只提供通用参考，应尊重儿童拒绝并避免强迫；完成情况不代表儿童能力、疾病风险或干预疗效，也不能替代专业评估。

## 常见问题

### 已选择 MP4，页面仍提示重新选择

先刷新页面并重新选择文件。当前版本会同步维护上传控件和内部文件状态，上传成功后会自动清空旧文件名；若页面仍保留旧界面，请重新执行 `run.bat`。

### MP4 上传成功但显示部分数据可用

这通常不是格式错误。侧脸、遮挡、画面过短、多人同框或只拍到手臂都会降低姿态或面部覆盖率。建议使用 5–30 秒、光线稳定、单人且脸部和上半身清晰的视频。

### 如何保存 PDF

在“综合历史”选择儿童、日期范围和记录类型，点击“预览报告”，确认内容加载完整后选择“打印 / 保存为 PDF”。系统打开的是浏览器打印对话框，不会在服务器后台伪造或长期保存 PDF 副本。

### 模型不可用

运行 `.venv\Scripts\python.exe scripts\check_models.py` 检查模型。缺失时运行 `scripts\download_models.py` 重新下载并验证官方模型。

### 端口被占用

`run.bat` 会检测 8001 和 5173 端口：如果是当前系统的健康服务，将直接复用；如果是其他程序占用，会显示对应 PID 和进程名，请关闭该程序后重试。
