# 基于深度学习的自闭症筛查与干预系统

这是一个面向儿童日常行为观察、早期筛查辅助和家庭互动管理的本地软件项目。当前仓库已完成**第二阶段：儿童档案管理与基础业务**。

> 本系统定位为教学科研与辅助观察工具，不属于医疗诊断软件，不替代专业医生的诊断和治疗意见。

## 已完成功能

- Vue 3、TypeScript、Vite、Element Plus、Vue Router 与 Axios 前端基础框架
- FastAPI、SQLAlchemy、Pydantic 与 SQLite 后端基础框架
- 首次管理员初始化、密码强度校验和防重复初始化
- PBKDF2-SHA256 带盐密码哈希，不保存明文密码
- 服务端会话、HttpOnly Cookie、登录校验与主动退出失效
- 真实数据库健康检查与受保护的系统信息接口
- 可折叠后台导航、系统首页、系统设置和五个有效占位路由
- 匿名化儿童档案的创建、查询、修改、详情与删除
- 后端自动生成唯一儿童编号，出生年月校验与年龄计算
- 按编号或昵称搜索、分页和建档时间排序
- 首页真实展示档案总数、本月新增和最近创建档案
- 可重复执行的 `0002_create_children` 数据库迁移
- `setup.bat`、`run.bat`、`check.bat` Windows 本地脚本
- 后端自动化测试、前端类型检查和生产构建

视频分析、行为观察、家庭训练和历史报告尚未开发。它们当前只有明确标注的占位页面，不包含模拟数据或无效按钮。

## 技术与环境

- Windows 10/11 64 位
- Python 3.11 或 3.12（优先 3.12）
- Node.js 20 或更高版本
- npm 10 或更高版本

本阶段不安装 PyTorch、TensorFlow、MediaPipe、OpenCV、Redis 或任务队列。

## 首次安装

在项目根目录双击：

```text
setup.bat
```

脚本会检查 Python、Node.js 和 npm，创建 `.venv`，安装依赖，创建 `data/app.db`，初始化基础数据表并执行前端类型检查。任何步骤失败都会显示具体错误并保留窗口。

## 启动系统

完成初始化后双击：

```text
run.bat
```

脚本会先检查依赖和端口，再分别启动后端和前端。只有在实际访问两个服务成功后才打开浏览器。

- 前端：<http://127.0.0.1:5173>
- 后端：<http://127.0.0.1:8001>
- API 文档：<http://127.0.0.1:8001/docs>

首次访问会显示管理员初始化表单。系统不提供默认账号或密码。

## 环境检查

双击：

```text
check.bat
```

脚本会检查版本、虚拟环境、依赖、数据库文件与表结构，并在服务已启动时检查前后端地址。检查结束后窗口会保留。

## 后端接口

| 方法 | 地址 | 说明 | 是否需登录 |
|---|---|---|---|
| GET | `/api/health` | 服务与 SQLite 真实健康检查 | 否 |
| GET | `/api/auth/status` | 管理员初始化状态 | 否 |
| POST | `/api/auth/initialize` | 首次创建单一管理员 | 否，仅首次 |
| POST | `/api/auth/login` | 管理员登录 | 否 |
| GET | `/api/auth/me` | 查询当前管理员 | 是 |
| POST | `/api/auth/logout` | 注销并使服务端会话失效 | 否 |
| GET | `/api/system/info` | 非敏感系统运行信息 | 是 |
| GET | `/api/children` | 档案搜索、分页与排序 | 是 |
| POST | `/api/children` | 创建儿童档案 | 是 |
| GET | `/api/children/{id}` | 获取档案详情 | 是 |
| PUT | `/api/children/{id}` | 更新档案 | 是 |
| DELETE | `/api/children/{id}` | 删除档案 | 是 |
| GET | `/api/dashboard/stats` | 首页真实档案统计 | 是 |

## 数据存储与安全

- 数据库：`data/app.db`
- 业务表：`children`；基础表：`users`、`auth_sessions`
- 迁移记录：`schema_migrations`
- 运行数据不会提交到 Git。
- 密码采用 PBKDF2-SHA256、随机盐和 310,000 次迭代保存。
- 浏览器仅保存 HttpOnly 会话 Cookie，前端 JavaScript 无法读取会话令牌。
- 会话令牌在数据库中只保存 SHA-256 摘要，退出后立即删除。
- 后端与前端默认只监听 `127.0.0.1`，不对公网开放。

本地运行并不等于绝对安全。请保护好电脑账户和磁盘数据，并避免在公共电脑保存敏感信息。

## 手动开发命令

后端：

```powershell
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 --reload --no-access-log
```

前端：

```powershell
cd frontend
npm run dev
```

测试：

```powershell
.venv\Scripts\python.exe -m pytest backend\tests -q
cd frontend
npm run typecheck
npm run build
```

## 配置

后端配置集中在 `backend/app/core/config.py`，支持以下环境变量：

- `APP_ENV`：运行模式，默认 `development`
- `APP_HOST`：后端监听地址，默认 `127.0.0.1`
- `APP_PORT`：后端端口，默认 `8001`
- `APP_DATA_DIR`：数据目录，默认项目根目录下的 `data`
- `FRONTEND_ORIGINS`：允许跨域访问的前端地址
- `LOG_LEVEL`：日志级别，默认 `INFO`

接口不会返回数据库路径、会话令牌、密码哈希或其他敏感配置。

## 常见问题

- **端口被占用**：关闭占用 8001 或 5173 端口的程序，然后重新运行 `run.bat`。
- **首次页面无法连接后端**：运行 `check.bat`，查看后端依赖、数据库和接口检查结果。
- **数据库无法创建**：确认当前用户对项目目录具有写入权限。
- **忘记管理员密码**：第一阶段未提供密码找回。请先备份数据；不要直接修改数据库中的密码哈希。

## 后续阶段衔接

第三阶段的视频分析可以通过 `children.id` 建立外键关联，并复用现有配置、数据库会话、认证依赖、统一请求封装、受保护路由和后台布局。新增业务表必须继续使用版本化迁移，不直接破坏已有 `users`、`auth_sessions` 与 `children` 数据。
