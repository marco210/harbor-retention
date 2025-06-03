FROM python:3.13-alpine
# Set the working directory
WORKDIR /app
RUN adduser -D appuser
# Set environment variables to prevent Python from writing .pyc files and to ensure output is sent straight to terminal
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN chown -R appuser:appuser /app
# Switch to the non-root user
USER appuser
# Copy the requirements file into the container
COPY requirements.txt .
# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt -i https://local_repository/repository/pypi/simple
# Copy the rest of the application code into the container
COPY main.py .

# Command to run the application
ENTRYPOINT  ["python3", "main.py"] 
