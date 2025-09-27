# 使用官方 Python 镜像作为基础镜像
FROM python:3.9-slim-buster

# 设置工作目录
WORKDIR /app

# 复制 requirements.txt 文件到工作目录
COPY requirements.txt .

# 安装依赖并显式检查streamlit是否安装成功
RUN pip install --no-cache-dir -r requirements.txt && \
    pip list | grep streamlit || (echo "Streamlit installation failed" && exit 1)

# 复制项目文件到工作目录
COPY . .

# 验证应用文件是否存在
RUN ls -la streamlit_app.py || (echo "streamlit_app.py not found" && exit 1)

# 暴露端口
EXPOSE 8501

# 定义启动命令，确保使用正确的参数
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
