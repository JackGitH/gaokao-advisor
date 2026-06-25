#!/bin/bash
# 高考志愿填报助手 - 安全部署脚本
# 用法: ./deploy.sh
#
# 约定：
# - 代码必须已经提交并推送到 origin/main。
# - 部署只操作服务器上的 gaokao Docker 服务，不影响同机其他服务。
# - 不在脚本中保存 GitHub token、密码等长期凭据。

set -e
set -o pipefail

# ======== 配置 ========
SERVER_IP="43.135.33.151"
SERVER_USER="ubuntu"
PEM_KEY="$(dirname "$0")/root.pem"
REMOTE_DIR="/home/ubuntu/apps/gaokao-advisor"
GITHUB_REPO="https://github.com/JackGitH/gaokao-advisor.git"
SERVICE_NAME="gaokao"
CONTAINER_NAME="gaokao-advisor"
PUBLIC_BASE="http://$SERVER_IP/gk"

# ======== 颜色输出 ========
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ======== 检查密钥 ========
if [ ! -f "$PEM_KEY" ]; then
    error "密钥文件不存在: $PEM_KEY"
fi
chmod 600 "$PEM_KEY"

SSH_CMD="ssh -i $PEM_KEY -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP"

# ======== Step 1: 本地 Git 状态检查 ========
info "检查本地 Git 状态..."
cd "$(dirname "$0")"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
    error "当前分支是 $CURRENT_BRANCH，请切到 main 后再部署"
fi

if [ -n "$(git status --porcelain)" ]; then
    git status --short
    error "存在未提交改动。请先提交并推送，再执行部署"
fi

git fetch origin main
LOCAL_HEAD=$(git rev-parse HEAD)
REMOTE_HEAD=$(git rev-parse origin/main)
if [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
    error "本地 main 与 origin/main 不一致。请先 pull/rebase 或 push 后再部署"
fi
info "本地代码已和 origin/main 对齐 ✓"

# ======== Step 2: 服务器拉取代码 ========
info "服务器拉取最新代码..."
$SSH_CMD "mkdir -p $REMOTE_DIR && cd $REMOTE_DIR && \
    if [ -d .git ]; then git pull --ff-only origin main; \
    else git clone $GITHUB_REPO .; fi"
info "代码拉取成功 ✓"

# ======== Step 3: Docker 构建并启动指定服务 ========
info "Docker 构建并启动 $SERVICE_NAME 服务..."
$SSH_CMD "cd $REMOTE_DIR && \
    docker compose up -d --build $SERVICE_NAME"
info "Docker 服务启动成功 ✓"

# ======== Step 4: 等待并验证 ========
info "等待服务启动..."
sleep 8

info "验证部署..."
HEALTH=$(curl -fsS "$PUBLIC_BASE/api/health" 2>/dev/null || true)
if echo "$HEALTH" | grep -q "ok"; then
    info "部署成功！服务运行正常 ✓"
    $SSH_CMD "cd $REMOTE_DIR && docker compose ps $SERVICE_NAME"
    echo ""
    echo "========================================="
    echo "  访问地址: $PUBLIC_BASE/"
    echo "  API接口:  $PUBLIC_BASE/api/recommend?score=600"
    echo "  健康检查: $PUBLIC_BASE/api/health"
    echo "========================================="
else
    warn "健康检查未通过，查看容器日志..."
    $SSH_CMD "docker logs $CONTAINER_NAME --tail 60"
    error "部署可能有问题，请检查日志"
fi
