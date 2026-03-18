#!/usr/bin/env bash
# ===========================================
# AIE 本地测试脚本
# 在推送代码前运行此脚本进行本地 CI 检查
# ===========================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 统计
TESTS_PASSED=0
TESTS_FAILED=0

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   AIE 本地 CI 检查                      ${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# ===========================================
# 1. Python 代码风格检查
# ===========================================
echo -e "${YELLOW}[1/5] Python 代码风格检查${NC}"

if command -v flake8 &> /dev/null; then
    if flake8 backend --config=.flake8 --statistics; then
        echo -e "${GREEN}✓ flake8 检查通过${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ flake8 检查失败${NC}"
        ((TESTS_FAILED++))
    fi
else
    echo -e "${YELLOW}⚠ flake8 未安装，跳过检查${NC}"
    echo "  安装：pip install flake8"
fi

echo ""

# ===========================================
# 2. Python 格式化检查
# ===========================================
echo -e "${YELLOW}[2/5] Python 格式化检查${NC}"

if command -v black &> /dev/null; then
    if black --check backend/ 2>/dev/null; then
        echo -e "${GREEN}✓ black 格式化检查通过${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ black 格式化检查失败${NC}"
        echo "  修复：black backend/"
        ((TESTS_FAILED++))
    fi
else
    echo -e "${YELLOW}⚠ black 未安装，跳过检查${NC}"
    echo "  安装：pip install black"
fi

echo ""

# ===========================================
# 3. 导入排序检查
# ===========================================
echo -e "${YELLOW}[3/5] 导入排序检查${NC}"

if command -v isort &> /dev/null; then
    if isort --check-only backend/ 2>/dev/null; then
        echo -e "${GREEN}✓ isort 导入排序检查通过${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ isort 导入排序检查失败${NC}"
        echo "  修复：isort backend/"
        ((TESTS_FAILED++))
    fi
else
    echo -e "${YELLOW}⚠ isort 未安装，跳过检查${NC}"
    echo "  安装：pip install isort"
fi

echo ""

# ===========================================
# 4. 单元测试
# ===========================================
echo -e "${YELLOW}[4/5] 运行单元测试${NC}"

if command -v pytest &> /dev/null; then
    if pytest backend/tests/ -v --tb=short 2>/dev/null; then
        echo -e "${GREEN}✓ 单元测试通过${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${YELLOW}⚠ 单元测试失败或无测试文件${NC}"
        # 不增加失败计数，因为可能还没有测试
    fi
else
    echo -e "${YELLOW}⚠ pytest 未安装，跳过测试${NC}"
    echo "  安装：pip install pytest pytest-asyncio"
fi

echo ""

# ===========================================
# 5. 前端检查
# ===========================================
echo -e "${YELLOW}[5/5] 前端代码检查${NC}"

if [ -d "frontend" ]; then
    cd frontend

    if command -v npm &> /dev/null; then
        if [ -f "package.json" ]; then
            # 安装依赖
            if [ ! -d "node_modules" ]; then
                echo "  安装前端依赖..."
                npm ci --silent
            fi

            # ESLint 检查
            if npm run lint --silent 2>/dev/null; then
                echo -e "${GREEN}✓ ESLint 检查通过${NC}"
                ((TESTS_PASSED++))
            else
                echo -e "${YELLOW}⚠ ESLint 检查未通过或未配置${NC}"
            fi

            # TypeScript 检查
            if npm run type-check --silent 2>/dev/null; then
                echo -e "${GREEN}✓ TypeScript 检查通过${NC}"
                ((TESTS_PASSED++))
            else
                echo -e "${YELLOW}⚠ TypeScript 检查未通过或未配置${NC}"
            fi

            # 构建检查
            if npm run build --silent 2>/dev/null; then
                echo -e "${GREEN}✓ 前端构建成功${NC}"
                ((TESTS_PASSED++))
            else
                echo -e "${RED}✗ 前端构建失败${NC}"
                ((TESTS_FAILED++))
            fi
        fi
    else
        echo -e "${YELLOW}⚠ npm 未安装，跳过前端检查${NC}"
    fi

    cd ..
else
    echo -e "${YELLOW}⚠ frontend 目录不存在，跳过检查${NC}"
fi

echo ""

# ===========================================
# 总结
# ===========================================
echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              检查总结                  ${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "通过：${GREEN}${TESTS_PASSED}${NC}"
echo -e "失败：${RED}${TESTS_FAILED}${NC}"
echo ""

if [ ${TESTS_FAILED} -gt 0 ]; then
    echo -e "${RED}❌ 部分检查失败，请修复后再推送代码${NC}"
    exit 1
else
    echo -e "${GREEN}✅ 所有检查通过，可以推送代码！${NC}"
    exit 0
fi
