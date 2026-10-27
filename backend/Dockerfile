# AWS Lambda container image for CropLens Agent.
# Python 3.12 + OpenCV 5 (opencv-python-headless==5.0.0.93).
# Build: see DEPLOY_AWS.md
FROM public.ecr.aws/lambda/python:3.12

# Install build deps for numpy/opencv wheels if needed, then clean up.
# opencv-python-headless ships manylinux wheels so no system OpenCV required.

# Copy requirements and install
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Verify OpenCV 5 at build time (fails the build if wrong version)
RUN python -c "import cv2; assert cv2.__version__.startswith('5'), cv2.__version__; print('OpenCV', cv2.__version__)"

# Copy application code
COPY app ${LAMBDA_TASK_ROOT}/app

# Environment-based configuration (override at deploy time)
ENV CROPLENS_ENV=aws \
    CROPLENS_CORS_MODE=lambda \
    CROPLENS_CORS_ORIGINS=* \
    CROPLENS_MAX_IMAGE_MB=12 \
    CROPLENS_MAX_VIDEO_MB=40 \
    CROPLENS_MAX_VIDEO_FRAMES=4

# Lambda handler = FastAPI app wrapped by Mangum
CMD [ "app.main.handler" ]
