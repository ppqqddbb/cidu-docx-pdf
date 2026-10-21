# 基于 MinerU 的结构化文档对比系统

本项目是一个专注于结构化文档对比的应用程序。**本系统的核心文档解析与对比算法是基于 [MinerU](https://github.com/opendatalab/MinerU) 进行集成与开发的。**

> ⚠️ **重要前置要求**：在运行本项目之前，请务必前往 GitHub 下载 **MinerU 源码**并完成其环境配置，确保基础解析功能正常。
> - **MinerU 源码地址**：[https://github.com/opendatalab/MinerU](https://github.com/opendatalab/MinerU)

## 🛠️ 环境准备

```bash
# 1. 安装后端依赖
pip install -r requirements.txt

# 2. 安装前端依赖
cd frontend
npm install

🧪 运行测试与构建
# 运行文档对比算法测试
pytest -q tests/comparison
# 预期输出: 25 passed

# 前端生产环境构建
cd frontend
npm run build

🚀 启动服务
1. 启动后端服务

bash
# (可选) 验证后端应用标题
python -c "from backend.main import app; print(app.title)"
# 预期输出: Structured Document Compare API

# 启动 FastAPI 后端
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
2. 启动前端服务

bash
cd frontend
npm run dev
🌐 访问系统
本机访问：http://127.0.0.1:5173

局域网访问：http://<本机局域网IP>:5173
