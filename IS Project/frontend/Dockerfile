# Use Python 3.11 slim image
FROM python:3.11-slim

# set the working directory in the container
WORKDIR /app

# copy the requirements file into the container
COPY requirements.txt .

# install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && \
    pip list | grep streamlit || (echo "Streamlit installation failed" && exit 1)

# copy the current directory contents into the container at /app
COPY . .

# verify that the main application file exists
RUN ls -la streamlit_app.py || (echo "streamlit_app.py not found" && exit 1)

# expose port 8501 for Streamlit
EXPOSE 8501

# define environment variable
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
