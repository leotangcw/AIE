#!/usr/bin/env bash
# ===========================================
# AIE 模型部署脚本
# 支持 Ollama、LocalAI 等本地模型部署
# ===========================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 默认配置
MODEL_PROVIDER="ollama"
MODEL_NAME="qwen2.5:7b"
ACTION="deploy"

# ===========================================
# 帮助信息
# ===========================================
show_help() {
    cat << EOF
🤖 AIE 模型部署脚本

用法：${0##*/} [选项]

选项:
    -p, --provider    模型提供商 (ollama|localai|fastchat)  默认：ollama
    -m, --model       模型名称  默认：qwen2.5:7b
    -a, --action      操作类型 (deploy|remove|status)  默认：deploy
    -h, --help        显示帮助信息

示例:
    # 部署 Ollama + qwen2.5:7b 模型
    ${0##*/} -p ollama -m qwen2.5:7b

    # 部署 LocalAI
    ${0##*/} -p localai

    # 查看状态
    ${0##*/} -a status

    # 移除模型部署
    ${0##*/} -a remove

EOF
}

# ===========================================
# 解析参数
# ===========================================
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--provider)
            MODEL_PROVIDER="$2"
            shift 2
            ;;
        -m|--model)
            MODEL_NAME="$2"
            shift 2
            ;;
        -a|--action)
            ACTION="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}❌ 未知选项：$1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# ===========================================
# 检查 GPU 支持
# ===========================================
check_gpu() {
    echo -e "${BLUE}🔍 检查 GPU 支持...${NC}"

    if command -v nvidia-smi &> /dev/null; then
        echo -e "${GREEN}✓ NVIDIA GPU 已检测${NC}"
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
        return 0
    else
        echo -e "${YELLOW}⚠️  未检测到 NVIDIA GPU，将使用 CPU 模式${NC}"
        return 1
    fi
}

# ===========================================
# 执行操作
# ===========================================
echo ""
echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   AIE 模型部署 - ${MODEL_PROVIDER}              ${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

case $ACTION in
    deploy)
        check_gpu || true

        echo -e "${GREEN}🚀 部署 ${MODEL_PROVIDER} 模型：${MODEL_NAME}...${NC}"

        # 创建/更新 .env.docker 文件
        if [ ! -f ".env.docker" ]; then
            echo -e "${YELLOW}⚠️  .env.docker 不存在，创建默认配置...${NC}"
            cp docker/.env.docker.example .env.docker
        fi

        # 更新配置
        echo "LLM_PROVIDER=${MODEL_PROVIDER}" >> .env.docker
        echo "LLM_MODEL=${MODEL_NAME}" >> .env.docker

        if [ "$MODEL_PROVIDER" == "ollama" ]; then
            echo "OLLAMA_MODEL=${MODEL_NAME}" >> .env.docker
        fi

        # 启动 Docker Compose
        docker-compose -f docker-compose.yml -f docker/docker-compose.models.yml \
            --profile models up -d

        echo ""
        echo -e "${GREEN}✅ 模型部署完成！${NC}"
        echo ""
        echo "📊 服务状态："
        docker-compose ps

        echo ""
        if [ "$MODEL_PROVIDER" == "ollama" ]; then
            echo "📝 模型信息："
            echo "   Ollama API: http://localhost:11434"
            echo "   模型：${MODEL_NAME}"
            echo ""
            echo "🔧 常用命令："
            echo "   # 查看已下载模型"
            echo "   docker exec aie-ollama ollama list"
            echo ""
            echo "   # 拉取新模型"
            echo "   docker exec aie-ollama ollama pull llama3.2:3b"
            echo ""
            echo "   # 测试模型"
            echo "   docker exec aie-ollama ollama run ${MODEL_NAME} 'Hello'"
        fi
        ;;

    remove)
        echo -e "${YELLOW}🗑️  移除模型部署...${NC}"

        docker-compose -f docker-compose.yml -f docker/docker-compose.models.yml \
            --profile models down -v

        echo -e "${GREEN}✅ 模型已移除${NC}"
        ;;

    status)
        echo -e "${BLUE}📊 模型服务状态：${NC}"
        echo ""

        docker-compose -f docker-compose.yml -f docker/docker-compose.models.yml \
            --profile models ps

        echo ""
        echo -e "${BLUE}📝 模型信息：${NC}"

        if [ "$MODEL_PROVIDER" == "ollama" ]; then
            docker exec aie-ollama ollama list 2>/dev/null || echo "Ollama 未运行"
        fi
        ;;

    logs)
        echo -e "${BLUE}📋 查看日志...${NC}"
        docker-compose -f docker-compose.yml -f docker/docker-compose.models.yml \
            --profile models logs -f
        ;;

    *)
        echo -e "${RED}❌ 未知操作：$ACTION${NC}"
        show_help
        exit 1
        ;;
esac

echo ""
