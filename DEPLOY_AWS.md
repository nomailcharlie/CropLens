# Deploying CropLens Agent to AWS Lambda (Container Image)

The OpenCV image processing runs in the **real AWS-hosted backend**, not in the
browser. This guide deploys the Python FastAPI service as an AWS Lambda
container image and exposes it through a Function URL.

> No AWS deployment is "complete" until *you* have configured credentials and a
> deployed endpoint. Do not hardcode AWS secrets — pass them via environment
> variables or the Lambda configuration.

---

## CORS architecture (read first)

Browsers reject responses with **two** `Access-Control-Allow-Origin` headers.
There are two CORS sources for a Lambda-Function-URL + FastAPI app:

1. **Lambda Function URL CORS config** (AWS-level) — answers `OPTIONS`
   preflight and can add CORS headers to responses.
2. **FastAPI `CORSMiddleware`** (app-level, `app/main.py`) — adds CORS headers
   when enabled.

To avoid duplicates, the backend uses a `CROPLENS_CORS_MODE` env var:

| Mode | When | Who handles CORS |
|------|------|-------------------|
| `app` (default) | local dev (`uvicorn`) | FastAPI `CORSMiddleware` only |
| `lambda` | AWS deployed | **Lambda Function URL CORS config only** — the app middleware is skipped |

The Dockerfile sets `CROPLENS_CORS_MODE=lambda`, so when running in the
container the app **does not** emit its own CORS headers. The Function URL CORS
config (set during `create-function-url-config` below) is the single source.
Locally (no Docker), the default `app` mode keeps `CORSMiddleware` active so
the Vite dev server works without any AWS config.

This is verified by `test_cors_local_mode_single_origin_header` in the backend
test suite (exactly one `Access-Control-Allow-Origin` on health, preflight, and
POST in `app` mode).

---

## Quick start (local, no AWS)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
# Frontend (other terminal): npm run dev   (Vite proxies /api -> :8080)
```

---

## AWS CloudShell runbook — region `ap-south-1` (Mumbai)

AWS CloudShell has the AWS CLI pre-installed and authenticated with your
console credentials, so no local install is needed. **Docker is NOT available
in CloudShell**, so the image build happens on your local machine (or a CI
runner with Docker) and CloudShell is used for ECR push, Lambda, and Function
URL management. Alternatively, run every command below from a local terminal
with the AWS CLI + Docker installed.

> Replace nothing with guessed values — every account-specific value is
> obtained from `aws sts get-caller-identity` or printed by a command. Do not
> invent account IDs or endpoints.

### A. One-time AWS Console steps (cannot be automated)

1. Sign in to the AWS Console at https://console.aws.amazon.com, region selector → **Asia Pacific (Mumbai) ap-south-1**.
2. (Optional) Create an IAM user with programmatic access and permissions for `lambda:*`, `ecr:*`, `iam:CreateRole`, `iam:AttachRolePolicy`, `logs:*`. If you are using CloudShell, your console role already has these.
3. Open **AWS CloudShell** (top-bar icon) to get a pre-authenticated shell in `ap-south-1`.

### B. Build the image (local machine with Docker)

The Dockerfile build context is the `backend/` directory (it contains
`Dockerfile`, `requirements.txt`, and `app/`).

```bash
# From the project root
cd backend
docker build --platform linux/amd64 -t croplens-agent:latest .
```

`--platform linux/amd64` is **required** because Lambda x86_64 expects an
amd64 image. Building on Apple Silicon without this flag produces an arm64
image that Lambda will reject.

The Dockerfile verifies OpenCV 5 at build time and fails the build if the
version is wrong:
```
 => RUN python -c "import cv2; assert cv2.__version__.startswith('5')..."
OpenCV 5.0.0
```

### C. Create the ECR repository and push (CloudShell or local)

```bash
AWS_REGION=ap-south-1
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPO=croplens-agent
ECR_URI=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO

aws ecr create-repository --repository-name $REPO --region $AWS_REGION
```

Log in to ECR (the password is valid for 12 hours):
```bash
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
```

Tag and push:
```bash
docker tag croplens-agent:latest $ECR_URI:latest
docker push $ECR_URI:latest
```

### D. Create the IAM execution role (one-time)

```bash
aws iam create-role --role-name lambda-exec-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  --region $AWS_REGION

aws iam attach-role-policy --role-name lambda-exec-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

ROLE_ARN=arn:aws:iam::$AWS_ACCOUNT_ID:role/lambda-exec-role
echo $ROLE_ARN
```

> If `lambda-exec-role` already exists, skip `create-role` and just attach the
> policy. The role only needs the basic execution policy (CloudWatch Logs).

### E. Create the Lambda function

```bash
aws lambda create-function \
  --function-name croplens-agent \
  --package-type Image \
  --code ImageUri=$ECR_URI:latest \
  --role $ROLE_ARN \
  --timeout 60 \
  --memory-size 2048 \
  --architectures x86_64 \
  --environment Variables={CROPLENS_ENV=aws,CROPLENS_CORS_MODE=lambda,CROPLENS_CORS_ORIGINS=*,CROPLENS_MAX_IMAGE_MB=12,CROPLENS_MAX_VIDEO_MB=40} \
  --region $AWS_REGION
```

`CROPLENS_CORS_MODE=lambda` **must** be set so the app middleware stays off and
the Function URL is the single CORS source (no duplicate headers).

### F. Create the Function URL with CORS

```bash
aws lambda create-function-url-config \
  --function-name croplens-agent \
  --auth-type NONE \
  --cors 'AllowOrigins=["*"],AllowMethods=["GET","POST","OPTIONS"],AllowHeaders=["Content-Type","Authorization","X-Client-Info","Apikey"],AllowCredentials=false,ExposeHeaders=["Content-Length"]' \
  --region $AWS_REGION
```

The response includes a `FunctionUrl` like
`https://<random>.lambda-url.ap-south-1.on.aws/`. **This is your
`VITE_API_BASE_URL`.** Copy it.

> Restrict `AllowOrigins` to your exact frontend domain (e.g.
> `https://yourapp.com`) in production instead of `*`.

### G. Test the deployed endpoint

```bash
ENDPOINT="https://<your-function-url>.lambda-url.ap-south-1.on.aws"

# 1. Health — must report the actual OpenCV version
curl -s "$ENDPOINT/health" | python3 -m json.tool
# Expect: opencv_version "5.0.0", runtime ".../ aws", status "ok"

# 2. OPTIONS preflight — exactly ONE Access-Control-Allow-Origin
curl -s -i -X OPTIONS "$ENDPOINT/analyze" \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  | grep -i "access-control-allow-origin"
# Expect exactly one line: Access-Control-Allow-Origin: *

# 3. GET /health CORS header — exactly ONE
curl -s -i "$ENDPOINT/health" -H "Origin: http://localhost:5173" \
  | grep -i "access-control-allow-origin"

# 4. POST /analyze with a real image (smoke test)
curl -s -X POST "$ENDPOINT/analyze" -F "file=@leaf.jpg" \
  | python3 -m json.tool | head -40
# Expect ok=true, opencv_version "5.0.0", final_action, passes, trace, limitations
```

If `grep -i "access-control-allow-origin"` returns **two** lines, the app
middleware is still active — confirm `CROPLENS_CORS_MODE=lambda` is set on the
function (step E) and redeploy.

### H. Check logs

```bash
aws logs tail /aws/lambda/croplens-agent --follow --region ap-south-1
```

### I. Update the function after code changes

```bash
# Rebuild (local, amd64) and push
cd backend
docker build --platform linux/amd64 -t croplens-agent:latest .
docker tag croplens-agent:latest $ECR_URI:latest
docker push $ECR_URI:latest

# Point Lambda at the new image and wait
aws lambda update-function-code \
  --function-name croplens-agent \
  --image-uri $ECR_URI:latest \
  --region ap-south-1

aws lambda wait function-updated --function-name croplens-agent --region ap-south-1

# Re-test health
curl -s "$ENDPOINT/health" | python3 -m json.tool
```

### J. Update Function URL CORS (if you change allowed origins)

```bash
aws lambda update-function-url-config \
  --function-name croplens-agent \
  --cors 'AllowOrigins=["https://yourapp.com"],AllowMethods=["GET","POST","OPTIONS"],AllowHeaders=["Content-Type","Authorization","X-Client-Info","Apikey"],AllowCredentials=false,ExposeHeaders=["Content-Length"]' \
  --region ap-south-1
```

---

## Connect the frontend

1. Create `.env` in the project root (next to `package.json`):
   ```bash
   cp .env.example .env
   # edit .env:
   VITE_API_BASE_URL=https://<your-function-url>.lambda-url.ap-south-1.on.aws
   ```
2. Rebuild and republish (Bolt deploys on build):
   ```bash
   npm run build
   ```
3. The header connection pill should show **Online · OpenCV 5.0.0**.
4. Live `/health` test from the browser console:
   ```js
   fetch(import.meta.env.VITE_API_BASE_URL + "/health").then(r => r.json()).then(console.log)
   ```
5. Smoke test: upload a real leaf photo in the dashboard and confirm the
   annotated result, quality flags, and decision trace appear. The backend is
   your AWS-hosted Lambda — the OpenCV version in the response should be `5.0.0`.

---

## Timeouts & limits

- Lambda timeout: **60s** (single-image OpenCV analysis is sub-second; margin
  covers cold starts and video frame sampling).
- Memory: **2048 MB** (OpenCV + numpy headroom).
- Architecture: **x86_64** (matches `--platform linux/amd64` build).
- Max image: 12 MB, max video: 40 MB (configurable via env vars).

## API Gateway alternative

If you need custom domains, throttling, or API keys, place an HTTP API Gateway
in front of the Lambda instead of a Function URL. The handler
(`app.main.handler`, Mangum-wrapped) is API-Gateway-compatible. In that case
set `CROPLENS_CORS_MODE=app` so the FastAPI middleware provides CORS, and
configure API Gateway CORS to **not** duplicate the headers (or let API
Gateway handle CORS and keep `CROPLENS_CORS_MODE=lambda`).

## Data & privacy

By default **no images are stored**. The Lambda decodes the upload into memory,
runs OpenCV, returns base64-encoded annotated images in the JSON response, and
discards the bytes. Temp files for video are created in `/tmp` and removed
immediately after analysis. There is no S3 or database dependency.
