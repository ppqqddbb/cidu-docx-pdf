pytest -q tests/comparison
# 25 passed

cd frontend
npm run build
# build passed

python -c "from backend.main import app; print(app.title)"
# Structured Document Compare API

# 后端：
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 前端：
cd frontend
npm run dev

# 本机访问：http://127.0.0.1:5173
# 局域网访问：http://<本机局域网 IP>:5173
