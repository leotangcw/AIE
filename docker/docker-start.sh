#!/usr/bin/env bash
# ===========================================
# AIE Docker 一键启动脚本
# ===========================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 默认配置
ENV_FILE="${PROJECT_ROOT}/.env.docker"
PROFILE="dev"
ACTION="up"

# ===========================================
# 帮助信息
# ===========================================
show_help() {
    cat << EOF
🐳 AIE Docker 一键启动脚本

用法：${0##*/} [选项]

选项:
    -p, --profile     环境配置 (ci|dev|prod)  默认：dev
    -a, --action      操作类型 (up|down|build|restart)  默认：up
    -e, --env         环境变量文件路径
    -h, --help        显示帮助信息

示例:
    # 启动开发环境
    ${0##*/} -p dev -a up

    # 启动 CI 环境
    ${0##*/} -p ci -a up

    # 启动生产环境
    ${0##*/} -p prod -a up

    # 构建镜像
    ${0##*/} -a build

    # 停止所有服务
    ${0##*/} -a down

EOF
}

# ===========================================
# 解析参数
# ===========================================
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--profile)
            PROFILE="$2"
            shift 2
            ;;
        -a|--action)
            ACTION="$2"
            shift 2
            ;;
        -e|--env)
            ENV_FILE="$2"
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

# ===========================================
# 检查前置条件
# ===========================================
echo -e "${BLUE}🔍 检查环境...${NC}"

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker 已安装: $(docker --version)${NC}"

# 检查 Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose 未安装${NC}"
    exit 1
fi

# 获取 docker-compose 命令
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi
echo -e "${GREEN}✓ Docker Compose 已安装${NC}"

# 检查环境变量文件
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}⚠️  环境变量文件不存在：$ENV_FILE${NC}"
    echo -e "${YELLOW}   将使用默认配置${NC}"
fi

# ===========================================
# 加载环境变量
# ===========================================
if [ -f "$ENV_FILE" ]; then
    echo -e "${BLUE}📁 加载环境变量：$ENV_FILE${NC}"
    set -a
    source "$ENV_FILE"
    set +a
fi

# ===========================================
# 执行操作
# ===========================================
cd "$PROJECT_ROOT"

echo ""
echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   AIE Docker ${PROFILE} 环境                    ${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

case $ACTION in
    up)
        echo -e "${GREEN}🚀 启动 ${PROFILE} 环境...${NC}"
        if [ "$PROFILE" == "ci" ]; then
            $COMPOSE_CMD --profile ci up -d
        elif [ "$PROFILE" == "dev" ]; then
            $COMPOSE_CMD --profile dev up -d
        elif [ "$PROFILE" == "prod" ]; then
            $COMPOSE_CMD --profile prod up -d --build
        fi
        echo -e "${GREEN}✅ 服务启动完成！${NC}"

        # 显示服务状态
        echo ""
        echo -e "${BLUE}📊 服务状态：${NC}"
        $COMPOSE_CMD ps

        # 显示访问信息
        echo ""
        if [ "$PROFILE" == "dev" ]; then
            echo -e "${GREEN}🌐 开发环境访问地址：${NC}"
            echo "   前端：http://localhost:3000"
            echo "   后端 API: http://localhost:8000"
            echo "   API 文档：http://localhost:8000/docs"
        elif [ "$PROFILE" == "prod" ]; then
            echo -e "${GREEN}🌐 生产环境访问地址：${NC}"
            echo "   应用：http://localhost"
        fi
        ;;

    down)
        echo -e "${YELLOW}🛑 停止所有服务...${NC}"
        $COMPOSE_CMD down
        echo -e "${GREEN}✅ 服务已停止${NC}"
        ;;

    build)
        echo -e "${GREEN}🔨 构建镜像...${NC}"
        $COMPOSE_CMD build
        echo -e "${GREEN}✅ 镜像构建完成${NC}"
        ;;

    restart)
        echo -e "${YELLOW}🔄 重启服务...${NC}"
        $COMPOSE_CMD restart
        echo -e "${GREEN}✅ 服务已重启${NC}"
        ;;

    logs)
        echo -e "${BLUE}📋 查看日志...${NC}"
        $COMPOSE_CMD logs -f
        ;;

    test)
        echo -e "${GREEN}🧪 运行 CI 测试...${NC}"
        $COMPOSE_CMD --profile ci up --abort-on-container-exit ci-test
        ;;

    *)
        echo -e "${RED}❌ 未知操作：$ACTION${NC}"
        show_help
        exit 1
        ;;
esac

echo ""
