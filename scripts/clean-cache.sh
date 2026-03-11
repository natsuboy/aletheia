#!/bin/bash
# Aletheia 项目缓存清理脚本
# 用于清理 Python、前端等生成的缓存文件

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🧹 Aletheia 项目缓存清理${NC}"
echo "======================================"

# 清理 Python 缓存
echo -e "\n${YELLOW}📦 清理 Python 缓存...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type f -name "*.pyd" -delete 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".eggs" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
echo -e "${GREEN}✅ Python 缓存已清理${NC}"

# 清理测试缓存
echo -e "\n${YELLOW}🧪 清理测试缓存...${NC}"
rm -rf .pytest_cache 2>/dev/null || true
rm -rf .coverage 2>/dev/null || true
rm -rf .hypothesis 2>/dev/null || true
rm -rf htmlcov 2>/dev/null || true
echo -e "${GREEN}✅ 测试缓存已清理${NC}"

# 清理前端缓存（可选）
echo -e "\n${YELLOW}🎨 清理前端缓存...${NC}"
if [ -d "src/frontend/node_modules" ]; then
    echo -e "${YELLOW}  警告: node_modules 目录存在${NC}"
    echo -e "${YELLOW}  如需清理，请手动运行: rm -rf src/frontend/node_modules${NC}"
fi
if [ -d "src/frontend/.vite" ]; then
    rm -rf src/frontend/.vite
    echo -e "${GREEN}  ✅ Vite 缓存已清理${NC}"
fi
if [ -d "src/frontend/dist" ]; then
    rm -rf src/frontend/dist
    echo -e "${GREEN}  ✅ 构建输出已清理${NC}"
fi

# 清理 IDE 缓存
echo -e "\n${YELLOW}💻 清理 IDE 缓存...${NC}"
find . -type d -name ".vscode" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".idea" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.swp" -delete 2>/dev/null || true
find . -type f -name "*.swo" -delete 2>/dev/null || true
find . -type f -name "*~" -delete 2>/dev/null || true
echo -e "${GREEN}✅ IDE 缓存已清理${NC}"

# 清理系统文件
echo -e "\n${YELLOW}🗑️  清理系统文件...${NC}"
find . -type f -name ".DS_Store" -delete 2>/dev/null || true
find . -type f -name "Thumbs.db" -delete 2>/dev/null || true
echo -e "${GREEN}✅ 系统文件已清理${NC}"

# 清理日志文件
echo -e "\n${YELLOW}📋 清理日志文件...${NC}"
find . -type f -name "*.log" -delete 2>/dev/null || true
echo -e "${GREEN}✅ 日志文件已清理${NC}"

# 清理临时 SCIP 文件
echo -e "\n${YELLOW}📄 清理临时 SCIP 文件...${NC}"
find . -type f -name "*.scip" -delete 2>/dev/null || true
echo -e "${GREEN}✅ SCIP 文件已清理${NC}"

# 清理数据库文件
echo -e "\n${YELLOW}🗄️  清理数据库文件...${NC}"
find . -type f -name "*.db" -delete 2>/dev/null || true
find . -type f -name "*.sqlite" -delete 2>/dev/null || true
find . -type f -name "*.sqlite3" -delete 2>/dev/null || true
echo -e "${GREEN}✅ 数据库文件已清理${NC}"

echo -e "\n${GREEN}======================================${NC}"
echo -e "${GREEN}✨ 缓存清理完成！${NC}"
echo ""
echo "提示：运行 'uv run pytest' 可以重新运行测试"
